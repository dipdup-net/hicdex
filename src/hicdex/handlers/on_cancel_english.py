from dipdup.context import HandlerContext
from dipdup.models import Transaction

import hicdex.models as models
from hicdex.types.objktbid_english.parameter.cancel_auction import CancelAuctionParameter
from hicdex.types.objktbid_english.storage import ObjktbidEnglishStorage


async def on_cancel_english(
    ctx: HandlerContext,
    cancel_auction: Transaction[CancelAuctionParameter, ObjktbidEnglishStorage],
) -> None:
    auction_model = await models.EnglishAuction.filter(id=int(cancel_auction.parameter.__root__)).get()
    auction_model.status = models.AuctionStatus.CANCELLED

    auction_model.update_level = cancel_auction.data.level
    auction_model.update_timestamp = cancel_auction.data.timestamp

    await auction_model.save()
