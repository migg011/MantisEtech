# Agenda de manutenção preventiva

No repositório do setor, abra **Novo equipamento** ou **Editar equipamento**. O campo **Nome do equipamento** fica imediatamente depois do tipo. Equipamentos existentes continuam válidos sem nome; nesse caso, as telas de preventivas usam o modelo ou o tipo como identificação.

Marque as preventivas aplicáveis: quinzenal, mensal, bimestral, trimestral, semestral e anual. Cada opção tem seu próprio **Próximo vencimento**. Sem data, o primeiro vencimento é calculado a partir do dia do cadastro da opção. �? possível informar um vencimento passado para acompanhar uma preventiva já atrasada. Desmarcar desativa os alertas da opção e preserva as execuções anteriores; reativá-la sem data mantém o prazo anterior. Uma OS aberta precisa ser concluída ou cancelada antes de alterar seu vencimento ou desmarcar a periodicidade.

Na **Central de Cadastros �?' Check List de Preventiva**, os alertas mostram todas as agendas ativas, começando pelos vencimentos mais antigos. Há filtros por situação e pesquisa por nome, tipo, patrimônio, série, setor ou linha. O painel atualiza a cada minuto enquanto a tela está aberta, usando a data de Manaus informada pelo servidor. Uma falha na consulta exibe aviso de dados possivelmente desatualizados.

- **Vencida:** prazo anterior à data atual, com a quantidade de dias em atraso.
- **Vence hoje:** prazo igual à data atual.
- **Em dia:** prazo futuro.

Equipamentos sem nenhuma opção marcada são contados separadamente: não possuem prazo acompanhado até a configuração de pelo menos uma periodicidade.

O botão **Roteiro** seleciona a máquina, seu tipo e a periodicidade no gerador. As máquinas disponíveis são somente as que têm aquela periodicidade marcada. Sem máquina selecionada, salve o roteiro padrão do tipo e frequência. Com uma máquina selecionada, salve seu roteiro específico ou use o padrão do tipo.

Emita uma OS numerada, com data e horário previstos e técnico responsável. O roteiro e a identificação do equipamento ficam preservados na OS. Após realizar a manutenção, abra **Preencher OS**, registre os resultados por atividade, a data e horário realizados, as peças substituídas e as observações. Você pode salvar parcialmente. **Concluir OS** registra o executor conectado e atualiza a agenda. Itens pendentes ou não realizados impedem a conclusão; não aplicáveis exigem justificativa. Veja [OS preventivas](ORDENS_PREVENTIVAS.md).

Na emissão, escolha se o novo vencimento parte do vencimento de referência (padrão, para preservar o calendário) ou da data realizada. Os intervalos são 15 dias para quinzenal e 1, 2, 3, 6 ou 12 meses de calendário para as demais. Se o dia não existir no mês de destino, usa-se o último dia válido. Se houver atraso acumulado, o próximo ciclo pode continuar vencido. Imprimir, salvar parcialmente ou cancelar a OS não atualiza a agenda.

Os alertas são exibidos no módulo, sem notificações externas. O histórico mostra as últimas 100 execuções. Técnicos e administradores acessam a agenda e registram execuções; a edição de um equipamento existente continua restrita ao administrador.

## Instalação

Na pasta `backend`, aplique a migração antes de iniciar a nova versão:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

A migração `0010` adiciona o nome e as tabelas de agenda/histórico. A `0011` adiciona as OS numeradas, roteiros específicos e a bimestral. As migrações não habilitam periodicidades automaticamente nem importam dados da planilha. Configure-as conforme o plano de manutenção de cada equipamento.

