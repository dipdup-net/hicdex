from dipdup.context import HandlerContext
from dipdup.models import Transaction

import hicdex.models as models
from hicdex.types.objktbid_marketplace.parameter.retract_ask import RetractAskParameter
from hicdex.types.objktbid_marketplace.storage import ObjktbidMarketplaceStorage


async def on_retract_ask(
    ctx: HandlerContext,
    retract_ask: Transaction[RetractAskParameter, ObjktbidMarketplaceStorage],
) -> None:
    ask = await models.Ask.filter(id=int(retract_ask.parameter.__root__)).get()
    ask.status = models.AuctionStatus.CANCELLED

    ask.update_level = retract_ask.data.level
    ask.update_timestamp = retract_ask.data.timestamp

    await ask.save()
