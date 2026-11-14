# Flivver Sell — Minecraft seller drafting tools

**Offline toolset. No Fiverr API integration, account connection, or automatic
publication.** Fiverr's public seller workflow does not expose a supported
API for accessing private orders, inbox messages or publishing Gigs. Fiverr's
terms prohibit unauthorized bots and automated extraction.

This extension helps create original Minecraft modpack work products, write
seller gig drafts and prepare deliverables that a human may review *later*.

## Activate in Static Code

1. Launch Static Code using your usual Linux launcher.
2. Run `/extension list` to see local extensions.
3. Run `/extension install fiverr-sell`, then type `INSTALL fiverr-sell`.
4. Ask Static: "Use the Fiverr seller extension to create a $5
   Minecraft Fabric modpack setup-service draft. Include a tested scope,
   realistic timing and a clear rights checklist."
5. Ask: "Export my draft for review."

To stop using the extension: `/extension disable fiverr-sell`.

## What it does

| Tool | Effect |
|---|---|
| `fiverr_sell_capabilities` | Show precise limitations |
| `fiverr_sell_draft_gig` | Store an unpublished draft (minimum $5) |
| `fiverr_sell_list_gigs` | List local drafts |
| `fiverr_sell_export_gig` | Produce downloadable Markdown review file |
| `fiverr_sell_pack_brief` | Create original modpack design, rights and testing checklist |
| `fiverr_sell_import_order` | Manually enter an order's necessary information |
| `fiverr_sell_list_orders` | See the local, unverified order ledger |
| `fiverr_sell_order_detail` | Read a manually entered order |
| `fiverr_sell_delivery_draft` | Generate an *unsent* delivery review note |

Data is stored in the workspace SQLite database, not in the repository.
All generated files are Static artifacts. Orders are not automatically
retrieved and revenue is **never treated as verified**.

### Restrictions

- No Fiverr login, scraping, gig publishing, payment handling, buyer messaging,
  direct delivery or automated order synchronization.
- No fabricated orders, reviews, test results or customer claims.
- No third-party mod files may be redistributed without checking permissions.
- Payment and client communication must remain in Fiverr, when permitted.
- Fiverr requires users to be at least 13; participants aged 13–17 require
  their parent/guardian's account and supervision. Users younger than 13 cannot
  use Fiverr.

Useful official references:

- https://www.fiverr.com/legal-portal/legal-terms/terms-of-service
- https://help.fiverr.com/hc/en-us/articles/360010451397-Creating-a-Gig
- https://help.fiverr.com/hc/en-us/articles/360010639617-A-freelancer-s-guide-to-the-Fiverr-order-process
- https://help.fiverr.com/hc/en-us/articles/32567580782609-Navigating-Fiverr-as-a-minor-How-to-stay-safe-and-compliant
