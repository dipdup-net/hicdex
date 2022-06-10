from dipdup.context import HandlerContext
from dipdup.models import Transaction

import hicdex.models as models
from hicdex.types.hdao_curation.parameter.claim_h_dao import ClaimHDAOParameter
from hicdex.types.hdao_curation.storage import HdaoCurationStorage


async def on_hdaoc_claim(
    ctx: HandlerContext,
    claim_h_dao: Transaction[ClaimHDAOParameter, HdaoCurationStorage],
) -> None:
    receiver, _ = await models.Holder.get_or_create(address=claim_h_dao.data.sender_address)
    receiver.hdao_balance += int(claim_h_dao.parameter.hDAO_amount)
    await receiver.save()

    token = await models.Token.filter(id=int(claim_h_dao.parameter.objkt_id)).get()
    token.hdao_balance -= int(claim_h_dao.parameter.hDAO_amount)
    await token.save()
