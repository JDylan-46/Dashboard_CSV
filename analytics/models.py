from django.db import models
import os

class Dataset(models.Model):
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='datasets/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    def delete(self, *args, **kwargs):
        # Eliminar el archivo físico cuando se elimina el modelo
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)