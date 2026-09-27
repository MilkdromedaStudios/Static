"""Replicate jobs survive browser disconnects and server restarts."""

import asyncio
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .db import now, uid
from .network import fetch_public


class MediaService:
    def __init__(self, config, store, artifacts, transport=None):
        self.config, self.store, self.artifacts, self.transport = (
            config,
            store,
            artifacts,
            transport,
        )
        self.sync_lock = asyncio.Lock()

    def profile(self, kind):
        profile = self.config.settings.media.get(kind)
        if not profile or not profile.model:
            raise ValueError(f"Configure a {kind} model and its cost reservation in Settings first")
        if not os.getenv("REPLICATE_API_TOKEN"):
            raise ValueError("Set REPLICATE_API_TOKEN on the server to enable media generation")
        return profile

    async def request(self, method, path, payload=None):
        async with httpx.AsyncClient(
            timeout=35, transport=self.transport, trust_env=False
        ) as client:
            r = await client.request(
                method,
                "https://api.replicate.com/v1" + path,
                json=payload,
                headers={
                    "Authorization": "Bearer " + os.getenv("REPLICATE_API_TOKEN", ""),
                    "Cancel-After": "10m",
                },
            )
            if r.status_code >= 400:
                raise ValueError(
                    f"Media provider returned HTTP {r.status_code}. Check the model schema, token and account limits."
                )
            return r.json()

    async def create(self, ctx, kind, prompt):
        if ctx.mode == "local":
            raise ValueError("Media APIs are disabled in local-only mode")
        profile = self.profile(kind)
        charge = self.store.reserve(
            ctx.run_id, profile.reserve_usd, f"media:{kind}", self.config.settings.daily_budget_usd
        )
        payload = {"input": {**profile.inputs, profile.prompt_field: prompt}}
        if ":" in profile.model:
            payload["version"] = profile.model.split(":", 1)[1]
            path = "/predictions"
        else:
            path = f"/models/{profile.model}/predictions"
        job_id = uid()
        self.store.execute(
            "INSERT INTO media_jobs VALUES(?,?,?,?,?,?,?,?,?)",
            (job_id, ctx.run_id, ctx.conversation_id, "", kind, "submitting", "[]", "", now()),
        )
        try:
            prediction = await self.request("POST", path, payload)
            prediction_id = prediction["id"]
            if not isinstance(prediction_id, str) or not prediction_id.isalnum():
                raise ValueError("Invalid prediction identifier from provider")
        except BaseException:
            self.store.execute(
                "UPDATE media_jobs SET status='unknown',error=? WHERE id=?",
                (
                    "Submission outcome is uncertain. Check your Replicate dashboard before retrying; the reservation is retained.",
                    job_id,
                ),
            )
            raise
        self.store.settle(
            charge
        )  # Keep conservative reservation; provider invoice is authoritative.
        self.store.execute(
            "UPDATE media_jobs SET prediction_id=?,status='starting' WHERE id=?",
            (prediction_id, job_id),
        )
        self.store.event(ctx.run_id, "media", {"id": job_id, "kind": kind, "status": "starting"})
        return {
            "job_id": job_id,
            "status": "starting",
            "note": "Job submitted. Track it in Files; Static will download the output when it finishes.",
        }

    async def refresh(self):
        async with self.sync_lock:
            jobs = self.store.query(
                "SELECT * FROM media_jobs WHERE status IN ('starting','processing')"
            )
            for job in jobs:
                try:
                    p = await self.request("GET", "/predictions/" + job["prediction_id"])
                    status = p["status"]
                    if status == "succeeded":
                        links = []

                        def collect(item):
                            if isinstance(item, str) and item.startswith("https://"):
                                links.append(item)
                            elif isinstance(item, list):
                                for value in item:
                                    collect(value)
                            elif isinstance(item, dict):
                                for value in item.values():
                                    collect(value)

                        collect(p.get("output"))
                        if not links:
                            raise ValueError(
                                "The model returned no downloadable HTTPS assets. Check its output schema."
                            )
                        outputs = []
                        for i, link in enumerate(links[:8]):
                            _, body, mime = await fetch_public(link, limit=50_000_000)
                            ext = Path(urlsplit(link).path).suffix.lower()
                            if ext not in (
                                ".png",
                                ".jpg",
                                ".jpeg",
                                ".webp",
                                ".gif",
                                ".mp4",
                                ".webm",
                                ".glb",
                                ".gltf",
                                ".obj",
                                ".stl",
                                ".ply",
                                ".zip",
                            ):
                                ext = {
                                    "image/png": ".png",
                                    "image/jpeg": ".jpg",
                                    "video/mp4": ".mp4",
                                    "model/gltf-binary": ".glb",
                                }.get(mime.split(";")[0], ".bin")
                            artifact = self.artifacts.save(
                                job["conversation_id"],
                                job["run_id"],
                                f"{job['kind']}-{job['id'][:6]}-{i + 1}{ext}",
                                body,
                                mime,
                            )
                            outputs.append(artifact)
                            self.store.event(job["run_id"], "artifact", artifact)
                        self.store.execute(
                            "UPDATE media_jobs SET status='succeeded',output=?,error='' WHERE id=?",
                            (json.dumps(outputs), job["id"]),
                        )
                    elif status in ("failed", "canceled"):
                        self.store.execute(
                            "UPDATE media_jobs SET status=?,error=? WHERE id=?",
                            (
                                status,
                                "Job did not complete. Check the provider dashboard for details.",
                                job["id"],
                            ),
                        )
                    else:
                        self.store.execute(
                            "UPDATE media_jobs SET status='processing',error='' WHERE id=?",
                            (job["id"],),
                        )
                except (httpx.HTTPError, ValueError, KeyError):
                    # A transient outage should not lose the prediction ID or submit it again.
                    self.store.execute(
                        "UPDATE media_jobs SET error=? WHERE id=?",
                        (
                            "Could not sync or download output. Retry from Files; the prediction ID has been retained.",
                            job["id"],
                        ),
                    )

    async def cancel(self, job_id):
        async with self.sync_lock:
            job = self.store.one("SELECT * FROM media_jobs WHERE id=?", (job_id,))
            if not job or job["status"] not in ("starting", "processing"):
                raise ValueError("No cancellable media job found")
            await self.request("POST", "/predictions/" + job["prediction_id"] + "/cancel")
            self.store.execute("UPDATE media_jobs SET status='canceled' WHERE id=?", (job_id,))

    async def loop(self):
        while True:
            try:
                await self.refresh()
            except Exception as exc:
                logging.getLogger(__name__).warning("Media sync failed (%s)", type(exc).__name__)
            await asyncio.sleep(10)
