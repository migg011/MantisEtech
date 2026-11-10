"""JSON mantém datas ISO e decimais como texto, conforme o contrato do Mantis."""
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.renderers import JSONRenderer


class MantisJSONRenderer(JSONRenderer):
    encoder_class = DjangoJSONEncoder
