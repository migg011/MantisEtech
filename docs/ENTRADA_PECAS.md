# Entrada simples de peças

Na lista de Spare Parts, abra a ficha pelo Part Number e selecione Estoque. Também é possível usar o menu de três pontos: Registrar quantidade inicial ou Entrada / Saída de peças.

## Primeiro registro

Informe a quantidade total que já possui. Isso cria o saldo inicial. A apresentação 00 UN antes da primeira contagem não significa que o estoque já foi conferido; o banco conserva o saldo não informado até a gravação.

## Recebimento de peças

Selecione Entrada de peças, preencha quantidade recebida e data. Observação, fornecedor e nota fiscal/documento são opcionais. A seção de fornecedor e documento pode ser expandida. Confira o saldo previsto e use Registrar entrada. O comando soma a quantidade ao estoque, registra responsável e horário e protege contra repetição após falha de rede.

## Saída e contagem

Saída para manutenção desconta as peças efetivamente retiradas e não permite saldo negativo. Solicitar uma peça para uma OS continua registrando uma necessidade, sem baixa automática. Ajustar contagem recebe a quantidade total encontrada e grava a diferença. A data informada descreve a movimentação; o saldo é atualizado na gravação, sem reordenar lançamentos anteriores.

## Consulta

Dados gerais reúne identificação e foto. Estoque contém recebimento, saída, contagem e histórico. Custos e reposição contém mínimo, máximo, ponto de reposição e custos de referência. A aba Ficha técnica foi retirada desta consulta. Os dados técnicos e fiscais anteriores não foram apagados; o fluxo de compras existente mantém suas regras próprias.

O recebimento simples não exige solicitação de compra aprovada e não altera automaticamente fornecedor preferencial ou custos do cadastro. Movimentações antigas conservam a data de registro original, sem receber data de recebimento ou fornecedor inventados.

## Código

Frontend: src/app/compartilhados/estoque-peca.component.ts, HTML e SCSS; ficha-peca.component.html organiza as abas. Backend: maintenance/estoque.py valida e grava saldo com histórico numa transação. A migração 0017_dados_entrada_estoque adiciona data_movimentacao, fornecedor_entrada e documento_entrada à tabela de movimentações. Os campos antigos permanecem preservados.
