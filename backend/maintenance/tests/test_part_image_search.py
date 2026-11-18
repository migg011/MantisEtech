import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from PIL import Image, ImageDraw
import zxingcpp

from maintenance.api import issue_token_value
from maintenance.models import SparePartCode, UserCode, SectorCode, LineCode


class PartImageSearchTests(TestCase):
    def test_photo_code_and_access(self):
        photo = Image.new('L', (160, 120), 240)
        ImageDraw.Draw(photo).polygon([(10, 90), (100, 10), (140, 80)], fill=20)
        original = io.BytesIO()
        photo.save(original, format='PNG')
        part = SparePartCode.objects.create(code='SP-001', part_number='N610113699AA',
                                            description='Nozzle', photo_data=original.getvalue())
        sector = SectorCode.objects.create(code='IMG', name='Setor')
        line = LineCode.objects.create(code='IMG', name='Linha', sector=sector)
        operator = UserCode.objects.create_user('IMG-OP', 'test-password', name='Operador', role='OPERADOR', line=line)
        admin = UserCode.objects.create_user('IMG-ADM', 'test-password', name='Admin', role='ADMINISTRADOR')
        path = '/api/spare-parts/image-search'

        def search(client, content):
            return client.post(path, {'image': SimpleUploadedFile('part.png', content)})

        self.assertEqual(search(Client(HTTP_AUTHORIZATION='Bearer ' + issue_token_value(operator)),
                                original.getvalue()).status_code, 403)
        client = Client(HTTP_AUTHORIZATION='Bearer ' + issue_token_value(admin))
        self.assertEqual(search(client, b'not an image').status_code, 400)
        result = search(client, original.getvalue())
        self.assertEqual(result.status_code, 200, result.content)
        match = result.json()['results'][0]
        self.assertEqual((match['id'], match['evidence'], match['visual_similarity']),
                         (part.pk, 'visual', 100))
        reframed = Image.new('L', (320, 240), 170)
        ImageDraw.Draw(reframed).polygon([(70, 190), (205, 70), (265, 175)], fill=30)
        image = io.BytesIO()
        reframed.save(image, format='PNG')
        result = search(client, image.getvalue()).json()
        self.assertEqual(result['results'][0]['id'], part.pk)

        image = io.BytesIO()
        Image.new('L', (160, 120), 100).save(image, format='PNG')
        self.assertEqual(search(client, image.getvalue()).json()['results'], [])
        qr = zxingcpp.create_barcode(part.part_number, zxingcpp.BarcodeFormat.QRCode)
        image = io.BytesIO()
        Image.fromarray(qr.to_image(scale=5)).save(image, format='PNG')
        result = search(client, image.getvalue()).json()
        self.assertEqual(result['codes'], [part.part_number])
        self.assertEqual(result['results'][0]['evidence'], 'codigo')
