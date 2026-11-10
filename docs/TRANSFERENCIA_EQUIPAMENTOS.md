# Transferência de equipamentos entre setores

No repositório do setor de origem, um administrador pode usar **Transferir** ao lado de uma máquina disponível. Escolha outro setor ativo, informe o motivo e confirme. A máquina sai da lista de origem e fica disponível no repositório de destino.

Se estiver alocada, primeiro use **Devolver ao repositório** na montagem da linha. O botão de transferência fica desabilitado enquanto houver alocação, e o servidor também confere essa condição.

O ID da máquina não muda. Fotos, manuais, medidas, agendas preventivas e OS continuam vinculados ao mesmo equipamento. O histórico registra origem, destino, responsável autenticado, data e motivo. Use **Histórico** no repositório para consultar movimentações.

A edição técnica continua impedindo a troca direta de setor. A transferência usa uma operação própria e transacional, com bloqueio da máquina e verificação do setor de origem para impedir ações sobre uma tela desatualizada.

Os campos de histórico são `setor_origem_id`, `setor_destino_id` e `motivo`, adicionados à tabela `movimentacoes_equipamento` pela migração `0013_transferencia_setores`. Movimentações antigas continuam válidas sem setor de origem/destino informado.
