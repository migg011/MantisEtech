# OS preventivas

O módulo usa o fluxo de trabalho do checklist Excel: selecionar a máquina, preparar as atividades, emitir uma OS, imprimir, executar e registrar cada item realizado.

## Roteiros

Na Central de Cadastros → Check List de Preventiva, selecione tipo e periodicidade. Sem equipamento selecionado, o roteiro é o padrão do tipo. Ao escolher uma máquina e salvar, é criado um roteiro específico para aquela máquina e frequência. **Usar roteiro padrão do tipo** remove a personalização, sem alterar OS emitidas.

O limite é de 100 atividades de até 500 caracteres cada, uma por linha. Textos bilíngues podem ser cadastrados na mesma atividade.

## Emissão e impressão

Selecione uma máquina com a periodicidade marcada no cadastro, salve o roteiro, informe a data prevista, o horário opcional e o técnico previsto. Escolha a regra do próximo prazo:

- **Manter calendário:** próximo prazo a partir do vencimento atual da agenda, independentemente do atraso da execução. Não pula ciclos vencidos.
- **A partir da execução:** próximo prazo a partir da data realizada.

**Emitir OS e baixar ficha** cria uma OS como `PREV-000001` e baixa seu arquivo HTML. Abra o arquivo e use **Imprimir / Salvar em PDF**. A ficha contém identificação, previsão, orientações de segurança, atividades, coluna de resultado, observações, peças substituídas e campos para assinatura.

Cada OS preserva seu roteiro e a identificação da máquina no momento da emissão. Reimpressões e consultas usam esses dados, mesmo após alterações no cadastro ou no roteiro. Só pode existir uma OS aberta por equipamento e periodicidade. Uma falha no download não desfaz a emissão: use **Imprimir** na lista de OS, sem criar outra.

## Preenchimento

Depois da manutenção, abra **Preencher OS**. Para cada item, selecione Pendente, Realizado, Não realizado ou Não aplicável. Não realizado e Não aplicável exigem justificativa. Informe a data realizada, o horário opcional, as observações e as peças efetivamente substituídas (descrição, código e quantidade).

**Salvar preenchimento** permite trabalho parcial sem atualizar o vencimento. **Imprimir versão salva** usa os últimos dados gravados no servidor. Para concluir, todos os itens devem estar realizados ou justificados como não aplicáveis, com ao menos um realizado. Data e horário futuros são recusados. A data precisa ser posterior à última execução da mesma agenda.

**Concluir OS** preserva os resultados, identifica o executor pelo usuário conectado e atualiza a agenda segundo a regra escolhida. O técnico previsto e o executor podem ser pessoas diferentes, e ambos ficam identificados. A assinatura manuscrita é feita na ficha; o sistema não cria uma assinatura gráfica.

Peças substituídas compõem o relatório da manutenção; não movimentam estoque nem criam solicitações de compra.

## Cancelamento e histórico

OS concluídas ou canceladas ficam disponíveis para consulta e impressão e não podem ser editadas. Cancelar exige justificativa, preserva o vencimento e libera uma nova emissão. Enquanto houver OS aberta, não é possível mudar o vencimento nem desmarcar sua periodicidade no cadastro.

A tela lista todas as OS abertas e as últimas 100 encerradas. O histórico anterior de execuções sem OS permanece consultável. Novas conclusões pela tela exigem a OS e seus itens. A API antiga de conclusão direta retorna conflito com orientação para emitir uma OS.

## Dados do Excel

Esta alteração implementa o fluxo e o formato dos registros, incluindo a bimestral. Os dados históricos da planilha não são importados automaticamente: nomes repetidos, datas em formatos misturados, registros sem periodicidade e status ausentes precisam ser conciliados antes de uma carga.
