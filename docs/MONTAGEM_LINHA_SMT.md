# Linha SMT montada a partir do repositório

1. Em **Setores �?' Repositório**, cadastre cada equipamento e sua foto frontal. Informe a altura em milímetros quando conhecida.
2. Em **Linhas SMT �?' Montagem da linha SMT**, escolha a linha, a máquina disponível e sua posição. Adicione os equipamentos na sequência da produção.
3. Use **Visualizar linha montada**. A tela usa os equipamentos da API, ordenados pela posição, sem depender de uma imagem única da linha.
4. A posição aparece acima da imagem e o nome do equipamento abaixo. Clique na imagem para consultar suas OS em uma janela sobre a linha. **Abrir nova OS** abre o formulário existente de registro de ocorrência. Feche os detalhes pelo botão de fechar, pela tecla Esc ou pelo fundo da janela.

## Como a imagem é montada

O nome superior vem do cadastro, com o tipo como alternativa. A foto cadastrada tem prioridade; na sua ausência, a tela usa a imagem local do tipo. Quando nenhuma imagem está disponível, aparece um ícone.

A largura visual acompanha a proporção da fotografia sem suas margens brancas ou transparentes. Esse recorte é feito somente na exibição: a foto original cadastrada permanece intacta. A escala do desenho usa uma altura comum para máquinas principais e uma altura menor, uniforme, para conveyors. As medidas técnicas continuam no cadastro e não determinam essa escala ilustrativa. As fotos não são esticadas. Linhas extensas podem ser percorridas lateralmente.

Esta representação é ilustrativa: o cadastro atual não tem um campo específico para o nível do transporte das placas. Fotos frontais, recortadas junto ao equipamento e com pouco espaço vazio, dão um resultado mais fiel. Não é um desenho dimensional de engenharia.

As OS são atualizadas a cada 15 segundos e filtradas pelo equipamento selecionado. A consulta existente fornece as OS ativas e as últimas 20 concluídas da linha; não é o histórico completo de todas as OS da máquina.

## Verificação visual sem alterar dados

O cenário `frontend/tests/smt-line.visual.ts` usa o componente real com dados fictícios e serviços locais. Ele não autentica usuários nem grava cadastros. Para compilá-lo, na pasta do frontend:

```powershell
npm run build -- --browser tests/smt-line.visual.ts --index tests/smt-line.visual.html --ts-config tests/tsconfig.visual.json --output-path .tmp-visual-linha-smt
```

Sirva a pasta `.tmp-visual-linha-smt/browser` e abra `linha-smt.visual.html`. Confira: detalhes ocultos inicialmente; máquina 6 mostra OS 42; máquina 13 mostra OS 43; máquina 1 não mostra essas OS; fechar oculta a tabela. Na largura de celular, apenas o panorama e a tabela devem rolar lateralmente.

