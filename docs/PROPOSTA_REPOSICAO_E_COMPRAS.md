# Proposta de reposição e lista de compras

Situação: desenho funcional para implementação. A automação descrita neste documento ainda não está implementada. Decisão do usuário: incluir na lista quando a última unidade for solicitada para uma OS, antes da retirada física.

## Solicitação e reserva

O saldo físico é a quantidade registrada no estoque. A reserva representa a parte desse saldo comprometida com solicitações de OS ainda pendentes. O disponível é o saldo físico menos as reservas válidas. Solicitar não dá baixa física. Cancelar uma solicitação libera a reserva. A retirada deve identificar a solicitação atendida, para reduzir o físico e encerrar a reserva sem desconto duplo.

Exemplo: físico 1, reservado 0, disponível 1. A OS solicita 1: físico 1, reservado 1, disponível 0. Nesse momento o item entra na lista de reposição. Pedidos que excedam o saldo precisam sinalizar falta, sem produzir disponível negativo ou reserva superior ao físico.

Solicitações antigas não podem ser convertidas indiscriminadamente em reservas: é necessário distinguir registros pendentes dos já atendidos. Esse tratamento deverá preservar o histórico e ser definido na migração.

## Lista de reposição

Uma peça deve possuir no máximo uma necessidade ativa de reposição, reunindo as origens em OS diferentes. Repetir o comando por falha de rede não pode duplicar a reserva ou o item. O item mostra Part Number, descrição, fabricante, unidade, saldo, reservas, origem e quantidade de compra a revisar. Não há aprovação nem envio automático.

A ficha da peça também pode permitir inclusão manual na lista, para compras antecipadas de preventiva ou reposição. Isso não transforma a peça em propriedade de uma máquina: o catálogo continua geral e a OS é apenas a origem da necessidade.

## Materiais avulsos

A lista também deve aceitar itens por descrição, quantidade, unidade, finalidade e observação, com Part Number opcional. Exemplos: luvas, álcool isopropílico, panos de limpeza, graxa e materiais para preventivas. Esses itens não exigem criar uma peça fictícia no catálogo nem entram automaticamente no controle de estoque de Spare Parts.

## Revisão e solicitação formal

O responsável revisa os itens e quantidades, inclui materiais avulsos, escolhe gestor e demais dados necessários e então gera a solicitação formal. A autorização e o encaminhamento permanecem explícitos. Solicitações em andamento devem ser consideradas para evitar compras duplicadas. Se uma necessidade deixar de existir, a lista deve sinalizar revisão, sem cancelar silenciosamente uma compra encaminhada.

## Dependências da implementação

O fluxo atual aceita somente peças cadastradas nos itens de compra e a solicitação direta de OS ainda não reserva estoque. Implementar esta proposta exige estados de solicitação e atendimento, reserva com bloqueios transacionais, lista de reposição persistida, suporte a materiais avulsos e revisão do formulário e das validações de compras. O recebimento simples já existente deverá permitir identificar atendimento de uma necessidade de reposição, preservando o histórico.

As regras de ficha técnica e fiscal do fluxo antigo de compras precisam ser separadas dos campos essenciais desta lista simples; não devem bloquear consumíveis avulsos sem uma regra de negócio explicitamente definida.

## Critérios de aceite

1. Solicitar a última unidade disponível cria reserva e uma necessidade de reposição, mantendo o saldo físico.
2. Duas solicitações simultâneas não reservam a mesma unidade duas vezes.
3. Pedidos sucessivos que esgotem o disponível também disparam a necessidade, mesmo que nenhum pedido individual corresponda ao saldo físico total.
4. Repetição do mesmo comando não duplica reservas ou itens.
5. Cancelamento libera reserva; atendimento dá baixa e encerra a reserva correspondente.
6. A lista aceita peças cadastradas e materiais avulsos, distinguindo suas origens.
7. Nenhuma solicitação é aprovada, enviada ao fornecedor ou paga automaticamente.
8. Histórico anterior, dados das peças e decisões de compra existentes permanecem preservados.
