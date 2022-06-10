from dipdup.context import HandlerContext
from dipdup.models import Transaction

import hicdex.models as models
from hicdex.types.objktbid_dutch.parameter.cancel_auction import CancelAuctionParameter
from hicdex.types.objktbid_dutch.storage import ObjktbidDutchStorage


async def on_cancel_dutch(
    ctx: HandlerContext,
    cancel_auction: Transaction[CancelAuctionParameter, ObjktbidDutchStorage],
) -> None:
    auction_model = await models.DutchAuction.filter(id=int(cancel_auction.parameter.__root__)).get()
    auction_model.status = models.AuctionStatus.CANCELLED

    auction_model.update_level = cancel_auction.data.level
    auction_model.update_timestamp = cancel_auction.data.timestamp

    await auction_model.save()
