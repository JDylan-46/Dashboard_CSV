from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Dataset
import pandas as pd
import json
import numpy as np
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
import os

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
        
        # Leer el archivo CSV con optimizaciones para archivos grandes
        df = pd.read_csv(dataset.file.path, 
                        low_memory=False,  # Evita warnings de tipos mixtos
                        dtype=str,         # Lee todo como string inicialmente
                        na_values=['', 'NA', 'N/A', 'null', 'NULL', 'None'])
        
        # Intentar convertir columnas numéricas
        for col in df.columns:
            try:
                # Intenta convertir a numérico
                numeric_series = pd.to_numeric(df[col], errors='coerce')
                # Si más del 70% son números válidos, considerarla numérica
                if numeric_series.notna().sum() / len(df) > 0.7:
                    df[col] = numeric_series
            except:
                pass  # Mantener como string si no se puede convertir
        
        # Análisis descriptivo básico
        analysis = {
            'basic_info': {
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': df.columns.tolist(),
                'memory_usage': df.memory_usage(deep=True).sum()
            },
            'missing_values': df.isnull().sum().to_dict(),
            'duplicates': int(df.duplicated().sum()),
            'data_types': df.dtypes.astype(str).to_dict(),
            'numeric_summary': {},
            'categorical_summary': {}
        }
        
        # Análisis para columnas numéricas (optimizado)
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        for col in numeric_columns[:10]:  # Limitar a 10 columnas numéricas para rendimiento
            try:
                col_data = df[col].dropna()  # Remover NaN para cálculos
                if len(col_data) > 0:
                    analysis['numeric_summary'][col] = {
                        'mean': float(col_data.mean()),
                        'median': float(col_data.median()),
                        'std': float(col_data.std()),
                        'min': float(col_data.min()),
                        'max': float(col_data.max()),
                        'unique_values': int(col_data.nunique())
                    }
            except Exception as e:
                # Si hay error en alguna columna, continuar con las demás
                continue
        
        # Análisis para columnas categóricas (optimizado)
        categorical_columns = df.select_dtypes(include=['object']).columns
        for col in categorical_columns[:10]:  # Limitar a 10 columnas categóricas para rendimiento
            try:
                col_data = df[col].dropna()  # Remover NaN
                if len(col_data) > 0:
                    value_counts = col_data.value_counts().head(10)
                    analysis['categorical_summary'][col] = {
                        'unique_values': int(col_data.nunique()),
                        'most_frequent': value_counts.to_dict()
                    }
            except Exception as e:
                # Si hay error en alguna columna, continuar con las demás
                continue
        
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