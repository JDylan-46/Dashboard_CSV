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
        with open(dataset.file.path, 'r', encoding='utf-8-sig') as file:
            # Detectar el delimitador
            sample = file.read(1024)
            file.seek(0)
            delimiter = ','
            if ';' in sample and sample.count(';') > sample.count(','):
                delimiter = ';'
            
            reader = csv.DictReader(file, delimiter=delimiter)
            rows = list(reader)
        
        if not rows:
            return Response({'error': 'CSV file is empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        column_names = list(rows[0].keys())
        total_rows = len(rows)
        
        # Análisis básico
        analysis = {
            'basic_info': {
                'rows': total_rows,
                'columns': len(column_names),
                'column_names': column_names,
                'memory_usage': len(str(rows))  # Aproximación simple
            },
            'missing_values': {},
            'duplicates': 0,
            'data_types': {},
            'numeric_summary': {},
            'categorical_summary': {}
        }
        
        # Analizar cada columna
        for col in column_names:
            values = [row[col] for row in rows]
            
            # Contar valores faltantes
            missing_count = sum(1 for v in values if v in ['', 'NULL', 'null', 'N/A', 'NA', None])
            analysis['missing_values'][col] = missing_count
            
            # Determinar tipo de datos
            non_empty_values = [v for v in values if v not in ['', 'NULL', 'null', 'N/A', 'NA', None]]
            
            if not non_empty_values:
                analysis['data_types'][col] = 'Empty'
                continue
            
            # Intentar determinar si es numérico
            numeric_count = 0
            numeric_values = []
            
            for val in non_empty_values[:100]:  # Tomar muestra de 100 valores
                try:
                    num_val = float(val.replace(',', '.'))
                    numeric_values.append(num_val)
                    numeric_count += 1
                except:
                    pass
            
            if numeric_count > len(non_empty_values) * 0.7:  # Si más del 70% son numéricos
                analysis['data_types'][col] = 'Numérico'
                
                # Estadísticas numéricas
                if numeric_values:
                    sorted_vals = sorted(numeric_values)
                    n = len(sorted_vals)
                    
                    analysis['numeric_summary'][col] = {
                        'mean': sum(sorted_vals) / n,
                        'median': sorted_vals[n//2] if n % 2 == 1 else (sorted_vals[n//2-1] + sorted_vals[n//2]) / 2,
                        'min': min(sorted_vals),
                        'max': max(sorted_vals),
                        'unique_values': len(set(sorted_vals))
                    }
                    
                    # Calcular desviación estándar
                    mean = analysis['numeric_summary'][col]['mean']
                    variance = sum((x - mean) ** 2 for x in sorted_vals) / n
                    analysis['numeric_summary'][col]['std'] = variance ** 0.5
            else:
                analysis['data_types'][col] = 'Texto'
                
                # Estadísticas categóricas
                value_counts = Counter(non_empty_values)
                most_common = dict(value_counts.most_common(10))
                
                analysis['categorical_summary'][col] = {
                    'unique_values': len(set(non_empty_values)),
                    'most_frequent': most_common
                }
        
        # Contar duplicados (comparación simple)
        seen = set()
        duplicates = 0
        for row in rows:
            row_str = str(sorted(row.items()))
            if row_str in seen:
                duplicates += 1
            else:
                seen.add(row_str)
        
        analysis['duplicates'] = duplicates
        
        return Response(analysis)
        
    except Dataset.DoesNotExist:
        return Response({'error': 'Dataset not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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