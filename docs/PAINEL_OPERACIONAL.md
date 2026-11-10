# Dashboard operacional MANTIS

A interface segue quatro blocos: indicadores principais; disponibilidade e tipos de OS; evolução diária; últimas OS. Os filtros de linha e de 7, 30 ou 90 dias consultam GET /api/dashboard. A consulta agregada não usa o limite de 200 registros de GET /api/orders.

## Definições dos indicadores

- Total de equipamentos: cadastros ativos no escopo atual.
- Equipamentos ativos: cadastros do escopo sem OS corretiva não concluída.
- Equipamentos em falha: equipamentos distintos com pelo menos uma OS corretiva não concluída. É uma classificação derivada das ordens, não um sinal de máquina em tempo real.
- Disponibilidade atual: equipamentos sem corretiva aberta / total de equipamentos ativos no escopo. Não representa disponibilidade temporal de produção. Sem equipamentos, o valor fica indisponível.
- OS abertas e backlog: corretivas não concluídas mais preventivas abertas, incluindo ordens anteriores ao período dos gráficos.
- MTTR: média das horas entre início do atendimento e conclusão das corretivas encerradas no período, somente com horários válidos. Mostra tamanho da amostra. Não usa tempo de espera desde a abertura.
- MTBF: indisponível até existir base confiável de horas reais de operação.
- Ordens por tipo: corretivas e preventivas emitidas no período. Preditivas ficam sem registro específico; nenhum volume é simulado no sistema real.
- Evolução: aberturas e conclusões por dia no fuso configurado. Uma OS antiga encerrada no período entra na curva de conclusões.
- Últimas OS: seis emissões mais recentes no período, incluindo os dois tipos. Os links levam à listagem correspondente.

## Para aprendizagem

Backend: maintenance/painel.py calcula os dados. maintenance/api.py valida parâmetros e perfis; maintenance/urls.py publica a rota. Frontend: src/app/funcionalidades/painel/painel.component.ts coordena consultas e traça os gráficos; HTML monta os blocos; SCSS define aparência e responsividade. Os gráficos usam SVG e CSS, sem instalar biblioteca adicional. Há comentários em português nos pontos principais.

Os testes usam bancos isolados. A prévia em tests/dashboard.visual.ts contém dados simulados apenas para conferência do layout, fora das rotas e do build normais. O dashboard real sempre lê o PostgreSQL pela API autenticada.
