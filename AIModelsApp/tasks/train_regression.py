from ..base_imports import *

def train_regression_model(ai_model, df, target_column):
    from pycaret.regression import setup, compare_models, tune_model, save_model
    
    try:
        logger.info(f"Iniciando regresión. DF shape: {df.shape}")
        logger.info(f"Target column: {target_column}")
        logger.info(f"Target values: {df[target_column].describe()}")
        
        # Setup con target_column recibido como parámetro
        setup(data=df, target=target_column, session_id=123, verbose=False)
        ai_model.progress = 40
        ai_model.save()
        
        logger.info("Setup completado, iniciando compare_models")
        
        # Compare models
        best_model = compare_models()
        
        ai_model.progress = 70
        ai_model.save()
        
        logger.info(f"Best model encontrado: {best_model}")
        
        # Tune model
        tuned_model = tune_model(best_model, verbose=False)
        ai_model.progress = 90
        ai_model.save()
        
        # Guardar modelo
        model_path = get_model_path(
            user=ai_model.user,
            model_type='regression',
            model_name=ai_model.name,
            model_id=ai_model.id
        )
        save_model(tuned_model, str(model_path))
        
        return {
            'model_name': str(best_model).split('(')[0],
            'model_path': str(model_path) + '.pkl'
        }
        
    except Exception as e:
        logger.error(f"Error en train_regression_model: {str(e)}")
        raise e