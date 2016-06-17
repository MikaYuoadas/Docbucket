from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Title')),
                ('document', models.FileField(upload_to=b'documents')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('last_access_on', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
