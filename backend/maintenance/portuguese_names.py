"""Dicionário de tradução: API/ORM antigos continuam compatíveis; o banco usa português.

db_table escolhe a tabela física. db_column escolhe a coluna física sem alterar
o nome que as telas existentes enviam à API. Não traduzimos palavras do Django.
"""

# Historical Django model names retained in migrations and permissions.
MODEL_NAMES = dict(zip(
    'User Sector Line EquipmentType Equipment EquipmentAttachment EquipmentMovement PreventiveChecklist EquipmentPreventive PreventiveOrder PreventiveExecution ProblemType WorkOrder LinePendency SparePart SparePartCompatibility SparePartTechnical PartRequisition PurchaseRequest PurchaseItem PurchaseEvent StockMovement MaterialCategory'.split(),
    'Usuario Setor Linha TipoEquipamento Equipamento AnexoEquipamento MovimentacaoEquipamento RoteiroPreventiva AgendaPreventiva OrdemPreventiva ExecucaoPreventiva TipoProblema OrdemServico PendenciaLinha PecaReposicao CompatibilidadePeca FichaTecnicaPeca SolicitacaoPeca SolicitacaoCompra ItemCompra EventoCompra MovimentacaoEstoque CategoriaMaterial'.split(),
))

TABLE_NAMES = dict(zip(
    'sectors lines users equipment_types equipment preventive_checklists equipment_preventives preventive_executions preventive_orders problem_types work_orders line_pendencies equipment_attachments equipment_movements spare_parts spare_part_compatibility spare_part_technical maintenance_part_requisitions spare_purchase_requests spare_purchase_request_items spare_purchase_events'.split(),
    'setores linhas usuarios tipos_equipamento equipamentos roteiros_preventiva agendas_preventiva execucoes_preventiva ordens_preventiva tipos_problema ordens_servico pendencias_linha anexos_equipamento movimentacoes_equipamento pecas_reposicao compatibilidade_pecas_equipamentos fichas_tecnicas_pecas solicitacoes_pecas_manutencao solicitacoes_compra itens_solicitacao_compra eventos_solicitacao_compra'.split(),
))

COLUMN_NAMES = {
    'id': 'id', 'code': 'codigo', 'name': 'nome', 'description': 'descricao',
    'active': 'ativo', 'created_at': 'criado_em', 'updated_at': 'atualizado_em',
    'sector': 'setor', 'line': 'linha', 'registration': 'matricula',
    'password': 'senha_hash', 'last_login': 'ultimo_acesso', 'role': 'perfil',
    'equipment_type': 'tipo_equipamento', 'equipment': 'equipamento',
    'frequency': 'periodicidade', 'items': 'itens', 'model_number': 'numero_modelo',
    'model': 'modelo', 'serial': 'numero_serie', 'manufacturer': 'fabricante',
    'manufacturing_date': 'data_fabricacao', 'manufacturing_date_text': 'data_fabricacao_texto',
    'length_mm': 'comprimento_mm', 'width_mm': 'largura_mm', 'height_mm': 'altura_mm',
    'weight_kg': 'peso_kg', 'voltage_v': 'tensao_v', 'frequency_hz': 'frequencia_hz',
    'current_a': 'corrente_a', 'power_w': 'potencia_w', 'pneumatic_pressure_bar': 'pressao_pneumatica_bar',
    'asset_number': 'numero_patrimonio', 'process_description': 'descricao_processo',
    'position': 'posicao', 'next_due': 'proximo_vencimento', 'last_performed': 'ultima_execucao',
    'checklist_items': 'itens_roteiro', 'schedule': 'agenda', 'performed_date': 'data_execucao',
    'previous_due': 'vencimento_anterior', 'technician': 'tecnico', 'notes': 'observacoes',
    'order': 'ordem_preventiva', 'status': 'situacao', 'expected_due': 'vencimento_previsto',
    'planned_date': 'data_planejada', 'planned_time': 'hora_planejada', 'recurrence_basis': 'base_recorrencia',
    'equipment_snapshot': 'retrato_equipamento', 'results': 'resultados',
    'safety_instructions': 'instrucoes_seguranca', 'parts': 'parts', 'performed_time': 'hora_execucao',
    'assigned_to': 'responsavel', 'assigned_name': 'nome_responsavel', 'created_by': 'criado_por',
    'finished_by': 'concluido_por', 'executor_name': 'nome_executor', 'finished_at': 'concluido_em',
    'cancellation_reason': 'motivo_cancelamento', 'revision': 'revisao', 'priority': 'prioridade',
    'opened_by': 'aberto_por', 'problem': 'problema', 'problem_type': 'tipo_problema',
    'root_cause': 'causa_raiz', 'corrective_action': 'acao_corretiva', 'preventive_action': 'acao_preventiva',
    'started_at': 'iniciado_em', 'downtime_seconds': 'tempo_parado_segundos', 'work_order': 'ordem_servico',
    'equipment_serial': 'serie_equipamento', 'resolved_by': 'resolvido_por', 'resolved_at': 'resolvido_em',
    'resolution': 'resolucao', 'kind': 'categoria', 'filename': 'nome_arquivo', 'mime_type': 'tipo_mime',
    'content': 'conteudo', 'size_bytes': 'tamanho_bytes', 'uploaded_by': 'enviado_por',
    'from_line': 'linha_origem', 'from_position': 'posicao_origem', 'to_line': 'linha_destino',
    'from_sector': 'setor_origem', 'to_sector': 'setor_destino', 'reason': 'motivo',
    'to_position': 'posicao_destino', 'action': 'acao', 'performed_by': 'executado_por',
    'part_number': 'numero_peca', 'category': 'categoria', 'unit': 'unidade',
    'minimum_stock': 'estoque_minimo', 'maximum_stock': 'estoque_maximo', 'reorder_point': 'ponto_reposicao',
    'storage_location': 'local_armazenamento', 'preferred_supplier': 'fornecedor_preferencial',
    'average_cost': 'custo_medio', 'last_cost': 'ultimo_custo', 'photo_filename': 'nome_arquivo_foto',
    'average_cost_currency': 'moeda_custo_medio', 'last_cost_currency': 'moeda_ultimo_custo',
    'photo_mime': 'tipo_mime_foto', 'photo_data': 'conteudo_foto',
    'datasheet_filename': 'nome_arquivo_ficha', 'datasheet_data': 'conteudo_ficha',
    'spare_part': 'peca', 'fiscal_status': 'situacao_fiscal', 'fiscal_validated_by': 'validado_por',
    'fiscal_validated_at': 'validado_em', 'quantity': 'quantidade', 'requester': 'solicitante',
    'note': 'observacao', 'purchase_type': 'tipo_compra', 'manager': 'gestor',
    'justification': 'justificativa', 'manager_comment': 'parecer_gestor', 'submitted_at': 'enviado_em',
    'decided_at': 'decidido_em', 'request': 'solicitacao', 'item_note': 'observacao_item',
    'technical_snapshot': 'retrato_ficha_tecnica', 'actor': 'autor', 'details': 'detalhes',
    'description_en': 'descricao_ingles', 'ncm': 'ncm', 'pli_description': 'descricao_pli',
    'description_pt': 'descricao_portugues', 'classification': 'classificacao',
    'independent_function': 'funcao_independente', 'connection_details': 'detalhes_conexoes',
    'useful_life': 'vida_util', 'asset_classification': 'classificacao_patrimonial',
    'main_function': 'funcao_principal', 'secondary_function': 'funcao_secundaria',
    'raw_material': 'materia_prima', 'intended_use': 'utilizacao', 'application_machine': 'maquina_aplicacao',
    'mechanical_electrical': 'mecanico_eletrico', 'current_type': 'tipo_corrente',
    'power': 'potencia', 'voltage': 'tensao', 'amperage': 'amperagem', 'picture_reference': 'referencia_imagem',
}
