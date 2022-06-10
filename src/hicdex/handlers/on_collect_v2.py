from dipdup.context import HandlerContext
from dipdup.models import Transaction

import hicdex.models as models
from hicdex.types.hen_swap_v2.parameter.collect import CollectParameter
from hicdex.types.hen_swap_v2.storage import HenSwapV2Storage


async def on_collect_v2(
    ctx: HandlerContext,
    collect: Transaction[CollectParameter, HenSwapV2Storage],
) -> None:
    swap = await models.Swap.filter(id=int(collect.parameter.__root__), contract_address=collect.data.target_address).get()
    seller = await swap.creator
    buyer, _ = await models.Holder.get_or_create(address=collect.data.sender_address)
    token = await swap.token.get()

    trade = models.Trade(
        swap=swap,
        seller=seller,
        buyer=buyer,
        token=token,
        amount=1,
        ophash=collect.data.hash,
        level=collect.data.level,
        timestamp=collect.data.timestamp,
    )
    await trade.save()

    swap.amount_left -= 1
    if swap.amount_left == 0:
        swap.status = models.SwapStatus.FINISHED
    await swap.save()
