from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Dataset
import json
import csv
from django.views.decorators.csrf import csrf_exempt
from collections import Counter
import io

def dashboard_view(request):
    """Vista principal del dashboard"""
    return render(request, 'dashboard.html')

@csrf_exempt
@api_view(['POST'])
def upload_dataset(request):
    """API para subir archivos CSV"""
    try:
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        name = request.data.get('name', file.name)
        
        # Verificar que sea un archivo CSV
        if not file.name.endswith('.csv'):
            return Response({'error': 'Only CSV files are allowed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Crear el dataset
        dataset = Dataset.objects.create(name=name, file=file)
        
        return Response({
            'id': dataset.id,
            'name': dataset.name,
            'uploaded_at': dataset.uploaded_at
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_dataset_analysis(request, dataset_id):
    """API para obtener análisis descriptivo del dataset"""
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        
        # Leer el archivo CSV usando el módulo csv nativo de Python
        try:
            # Abrir el archivo directamente desde el FileField
            file_content = dataset.file.read().decode('utf-8-sig')
            lines = file_content.splitlines()
            
            if not lines:
                return Response({'error': 'CSV file is empty'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Detectar el delimitador
            first_line = lines[0]
            delimiter = ','
            if ';' in first_line and first_line.count(';') > first_line.count(','):
                delimiter = ';'
            
            # Parsear CSV manualmente
            reader = csv.DictReader(lines, delimiter=delimiter)
            rows = list(reader)
            
        except Exception as e:
            return Response({'error': f'Error reading CSV file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not rows:
            return Response({'error': 'CSV file has no data rows'}, status=status.HTTP_400_BAD_REQUEST)
        
        column_names = list(rows[0].keys())
        total_rows = len(rows)
        
        # Análisis básico
        analysis = {
            'basic_info': {
                'rows': total_rows,
                'columns': len(column_names),
                'column_names': column_names,
                'memory_usage': len(file_content)  # Tamaño del archivo
            },
            'missing_values': {},
            'duplicates': 0,
            'data_types': {},
            'numeric_summary': {},
            'categorical_summary': {}
        }
        
        # Analizar cada columna (limitar a primeras 10 para rendimiento)
        for col in column_names[:10]:
            values = [row.get(col, '') for row in rows]
            
            # Contar valores faltantes
            missing_count = sum(1 for v in values if not v or v.strip() in ['', 'NULL', 'null', 'N/A', 'NA', 'None'])
            analysis['missing_values'][col] = missing_count
            
            # Determinar tipo de datos
            non_empty_values = [v.strip() for v in values if v and v.strip() and v.strip() not in ['', 'NULL', 'null', 'N/A', 'NA', 'None']]
            
            if not non_empty_values:
                analysis['data_types'][col] = 'Empty'
                continue
            
            # Intentar determinar si es numérico
            numeric_count = 0
            numeric_values = []
            
            # Tomar muestra más pequeña para mejor rendimiento
            sample_size = min(50, len(non_empty_values))
            sample_values = non_empty_values[:sample_size]
            
            for val in sample_values:
                try:
                    # Limpiar el valor antes de convertir
                    clean_val = str(val).replace(',', '.').replace(' ', '')
                    if clean_val:
                        num_val = float(clean_val)
                        numeric_values.append(num_val)
                        numeric_count += 1
                except:
                    pass
            
            if numeric_count > len(sample_values) * 0.6:  # Si más del 60% son numéricos
                analysis['data_types'][col] = 'Numérico'
                
                # Estadísticas numéricas
                if numeric_values:
                    sorted_vals = sorted(numeric_values)
                    n = len(sorted_vals)
                    
                    mean_val = sum(sorted_vals) / n
                    median_val = sorted_vals[n//2] if n % 2 == 1 else (sorted_vals[n//2-1] + sorted_vals[n//2]) / 2
                    
                    analysis['numeric_summary'][col] = {
                        'mean': round(mean_val, 2),
                        'median': round(median_val, 2),
                        'min': round(min(sorted_vals), 2),
                        'max': round(max(sorted_vals), 2),
                        'unique_values': len(set(sorted_vals)),
                        'std': 0  # Inicializar
                    }
                    
                    # Calcular desviación estándar
                    if n > 1:
                        variance = sum((x - mean_val) ** 2 for x in sorted_vals) / n
                        analysis['numeric_summary'][col]['std'] = round(variance ** 0.5, 2)
            else:
                analysis['data_types'][col] = 'Texto'
                
                # Estadísticas categóricas (tomar muestra para rendimiento)
                sample_categorical = non_empty_values[:100]  # Máximo 100 valores
                value_counts = {}
                for val in sample_categorical:
                    value_counts[val] = value_counts.get(val, 0) + 1
                
                # Obtener los 5 más frecuentes
                most_frequent = dict(sorted(value_counts.items(), key=lambda x: x[1], reverse=True)[:5])
                
                analysis['categorical_summary'][col] = {
                    'unique_values': len(set(non_empty_values)),
                    'most_frequent': most_frequent
                }
        
        # Contar duplicados (muestra pequeña para rendimiento)
        sample_rows = rows[:1000]  # Solo los primeros 1000 para evitar timeout
        seen = set()
        duplicates = 0
        for row in sample_rows:
            # Crear hash simple de la fila
            row_hash = hash(tuple(sorted((k, v) for k, v in row.items() if v)))
            if row_hash in seen:
                duplicates += 1
            else:
                seen.add(row_hash)
        
        analysis['duplicates'] = duplicates
        
        return Response(analysis)
        
    except Dataset.DoesNotExist:
        return Response({'error': 'Dataset not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error processing dataset: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def list_datasets(request):
    """API para listar todos los datasets"""
    datasets = Dataset.objects.all()
    data = []
    for dataset in datasets:
        data.append({
            'id': dataset.id,
            'name': dataset.name,
            'uploaded_at': dataset.uploaded_at
        })
    return Response(data)