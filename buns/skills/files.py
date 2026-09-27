import math
from typing import Literal

from pydantic import Field

from ..config import StrictModel
from .base import Skill


class Write(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    format: Literal["txt", "md", "json", "csv", "html", "docx", "pdf"]
    content: str = Field(min_length=1, max_length=100000)


class Read(StrictModel):
    artifact_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class Empty(StrictModel):
    pass


class Mesh(StrictModel):
    name: str = Field(default="model", max_length=100)
    shape: Literal["cube", "sphere", "cylinder"]
    size: float = Field(default=1, gt=0, le=1000)


class Media(StrictModel):
    kind: Literal["image", "video", "3d"]
    prompt: str = Field(min_length=5, max_length=4000)


async def write(ctx, args):
    result = ctx.artifacts.document(
        ctx.conversation_id, ctx.run_id, args.name, args.format, args.content
    )
    ctx.store.event(ctx.run_id, "artifact", result)
    return result


async def read(ctx, args):
    return {
        "untrusted_file_content": True,
        "text": ctx.artifacts.text(args.artifact_id, ctx.conversation_id),
    }


async def list_files(ctx, args):
    return ctx.store.query(
        "SELECT id,name,size,mime FROM artifacts WHERE conversation_id=? ORDER BY created DESC",
        (ctx.conversation_id,),
    )


async def mesh(ctx, args):
    s, vertices, faces = args.size / 2, [], []
    if args.shape == "cube":
        vertices = [
            (x * s, y * s, z * s)
            for x, y, z in [
                (-1, -1, -1),
                (1, -1, -1),
                (1, 1, -1),
                (-1, 1, -1),
                (-1, -1, 1),
                (1, -1, 1),
                (1, 1, 1),
                (-1, 1, 1),
            ]
        ]
        faces = [(1, 4, 3, 2), (5, 6, 7, 8), (1, 2, 6, 5), (4, 8, 7, 3), (1, 5, 8, 4), (2, 3, 7, 6)]
    elif args.shape == "sphere":
        n, rings = 32, 16
        vertices = [(0, 0, s)]
        for j in range(1, rings):
            for i in range(n):
                a, b = 2 * math.pi * i / n, math.pi * j / rings
                vertices.append(
                    (s * math.sin(b) * math.cos(a), s * math.sin(b) * math.sin(a), s * math.cos(b))
                )
        vertices.append((0, 0, -s))
        bottom = len(vertices)
        for i in range(n):
            faces.append((1, 2 + i, 2 + (i + 1) % n))
            for j in range(rings - 2):
                a, b = 2 + j * n + i, 2 + j * n + (i + 1) % n
                faces.append((a, a + n, b + n, b))
            faces.append((bottom, 2 + (rings - 2) * n + (i + 1) % n, 2 + (rings - 2) * n + i))
    else:
        n = 32
        vertices = [
            (s * math.cos(2 * math.pi * i / n), s * math.sin(2 * math.pi * i / n), z)
            for z in (-s, s)
            for i in range(n)
        ]
        for i in range(n):
            a, b = i + 1, (i + 1) % n + 1
            faces.append((a, b, b + n, a + n))
        faces.extend([tuple(range(n, 0, -1)), tuple(range(n + 1, 2 * n + 1))])
    content = (
        "# Buns procedural mesh; units are arbitrary\n"
        + "\n".join("v %.6f %.6f %.6f" % v for v in vertices)
        + "\n"
        + "\n".join("f " + " ".join(map(str, f)) for f in faces)
        + "\n"
    )
    result = ctx.artifacts.save(
        ctx.conversation_id, ctx.run_id, args.name + ".obj", content.encode(), "text/plain"
    )
    ctx.store.event(ctx.run_id, "artifact", result)
    return result


async def media(ctx, args):
    return await ctx.media.create(ctx, args.kind, args.prompt)


def register(registry):
    registry.add(
        Skill(
            "file_create",
            "Create a downloadable file or document. PDF and DOCX support # headings and plain paragraphs; CSV and JSON must contain valid data. HTML is downloaded, never executed by Buns.",
            "Files",
            Write,
            write,
        )
    )
    registry.add(
        Skill(
            "file_read",
            "Read UTF-8 text or a text PDF uploaded/generated in the current conversation using its artifact ID.",
            "Files",
            Read,
            read,
        )
    )
    registry.add(
        Skill(
            "file_list",
            "List available files in this conversation and their IDs.",
            "Files",
            Empty,
            list_files,
        )
    )
    registry.add(
        Skill(
            "mesh_create",
            "Create a free procedural cube, sphere or cylinder as a real OBJ 3D mesh. This is simple geometry, not text-to-3D AI.",
            "Create",
            Mesh,
            mesh,
        )
    )
    registry.add(
        Skill(
            "media_generate",
            "Generate an image, video or 3D asset with the operator-configured Replicate model. Requires a configured profile, API key and explicit user approval. Returns a tracked background job. Never claim it is finished until the job succeeds.",
            "Create",
            Media,
            media,
            approval=True,
        )
    )
