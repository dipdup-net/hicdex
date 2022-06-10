from dipdup.context import HandlerContext
from dipdup.models import Transaction

import hicdex.models as models
from hicdex.types.objktbid_marketplace.parameter.retract_bid import RetractBidParameter
from hicdex.types.objktbid_marketplace.storage import ObjktbidMarketplaceStorage


async def on_retract_bid(
    ctx: HandlerContext,
    retract_bid: Transaction[RetractBidParameter, ObjktbidMarketplaceStorage],
) -> None:
    bid = await models.Bid.filter(id=int(retract_bid.parameter.__root__)).get()
    bid.status = models.AuctionStatus.CANCELLED

    bid.update_level = retract_bid.data.level
    bid.update_timestamp = retract_bid.data.timestamp

    await bid.save()
