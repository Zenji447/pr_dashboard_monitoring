"""
Servicio para gestionar reglas de validación de PRs.
Proporciona funciones para cargar, guardar, crear, actualizar y eliminar reglas.
"""

import json
import logging
from integrations.state import (
    load_pr_validation_rules,
    save_pr_validation_rules,
    load_custom_rules,
    save_custom_rules,
    get_all_validation_rules,
    log_rule_change,
)

logger = logging.getLogger("rules_service")


def get_all_rules():
    """Obtiene todas las reglas (branch + custom)."""
    return get_all_validation_rules()


def get_branch_rules():
    """Obtiene solo las reglas de branch."""
    return load_pr_validation_rules()


def get_custom_rules():
    """Obtiene solo las reglas personalizadas."""
    return load_custom_rules()


def update_branch_rule(branch_name, rule_data, changed_by=None, ip_address=None):
    """
    Actualiza una regla de branch existente.
    
    Args:
        branch_name: Nombre de la rama (ej: 'develop', 'develop-pr')
        rule_data: Dict con los datos de la regla
        changed_by: Usuario que hace el cambio
        ip_address: IP del usuario
    
    Returns:
        Dict con la regla actualizada o error
    """
    try:
        rules = load_pr_validation_rules()
        
        if branch_name not in rules:
            return {"ok": False, "error": f"Rama '{branch_name}' no encontrada"}
        
        # Guardar valor anterior para auditoría
        old_value = json.dumps(rules[branch_name])
        
        # Actualizar campos permitidos
        allowed_fields = ["enabled", "release_pattern", "release_message", 
                         "sprints", "sprint_message", "warning_message"]
        
        for field in allowed_fields:
            if field in rule_data:
                rules[branch_name][field] = rule_data[field]
        
        save_pr_validation_rules(rules)
        
        # Registrar cambio en historial
        new_value = json.dumps(rules[branch_name])
        log_rule_change(branch_name, "branch", "update", old_value, new_value, changed_by, ip_address)
        
        logger.info(f"Regla de branch '{branch_name}' actualizada por {changed_by or 'unknown'}")
        
        return {"ok": True, "rule": rules[branch_name]}
    except Exception as e:
        logger.error(f"Error actualizando regla de branch: {e}")
        return {"ok": False, "error": str(e)}


def create_custom_rule(rule_id, rule_data):
    """
    Crea una nueva regla personalizada.
    
    Args:
        rule_id: ID único para la regla
        rule_data: Dict con los datos de la regla
    
    Returns:
        Dict con la regla creada o error
    """
    try:
        rules = load_custom_rules()
        
        if rule_id in rules:
            return {"ok": False, "error": f"Regla '{rule_id}' ya existe"}
        
        # Validar campos requeridos
        required_fields = ["name", "type"]
        for field in required_fields:
            if field not in rule_data or not rule_data[field]:
                return {"ok": False, "error": f"Campo requerido: {field}"}
        
        # Crear regla con valores por defecto
        new_rule = {
            "name": rule_data.get("name", "Nueva Regla"),
            "description": rule_data.get("description", ""),
            "enabled": rule_data.get("enabled", True),
            "type": rule_data.get("type", "file_pattern"),
            "pattern": rule_data.get("pattern", ".*"),
            "validation_type": rule_data.get("validation_type", "exists"),
            "validation_pattern": rule_data.get("validation_pattern", ""),
            "error_message": rule_data.get("error_message", "Validación fallida"),
            "severity": rule_data.get("severity", "warning")
        }
        
        rules[rule_id] = new_rule
        save_custom_rules(rules)
        logger.info(f"Regla personalizada '{rule_id}' creada")
        
        return {"ok": True, "rule": new_rule}
    except Exception as e:
        logger.error(f"Error creando regla personalizada: {e}")
        return {"ok": False, "error": str(e)}


def update_custom_rule(rule_id, rule_data):
    """
    Actualiza una regla personalizada existente.
    
    Args:
        rule_id: ID de la regla
        rule_data: Dict con los datos a actualizar
    
    Returns:
        Dict con la regla actualizada o error
    """
    try:
        rules = load_custom_rules()
        
        if rule_id not in rules:
            return {"ok": False, "error": f"Regla '{rule_id}' no encontrada"}
        
        # Actualizar campos permitidos
        allowed_fields = ["name", "description", "enabled", "type", "pattern",
                         "validation_type", "validation_pattern", "error_message", "severity"]
        
        for field in allowed_fields:
            if field in rule_data:
                rules[rule_id][field] = rule_data[field]
        
        save_custom_rules(rules)
        logger.info(f"Regla personalizada '{rule_id}' actualizada")
        
        return {"ok": True, "rule": rules[rule_id]}
    except Exception as e:
        logger.error(f"Error actualizando regla personalizada: {e}")
        return {"ok": False, "error": str(e)}


def delete_custom_rule(rule_id):
    """
    Elimina una regla personalizada.
    
    Args:
        rule_id: ID de la regla a eliminar
    
    Returns:
        Dict con resultado de la operación
    """
    try:
        rules = load_custom_rules()
        
        if rule_id not in rules:
            return {"ok": False, "error": f"Regla '{rule_id}' no encontrada"}
        
        del rules[rule_id]
        save_custom_rules(rules)
        logger.info(f"Regla personalizada '{rule_id}' eliminada")
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error eliminando regla personalizada: {e}")
        return {"ok": False, "error": str(e)}


def toggle_rule(rule_type, rule_id):
    """
    Activa/desactiva una regla.
    
    Args:
        rule_type: 'branch' o 'custom'
        rule_id: ID de la regla
    
    Returns:
        Dict con el nuevo estado o error
    """
    try:
        if rule_type == "branch":
            rules = load_pr_validation_rules()
            if rule_id not in rules:
                return {"ok": False, "error": f"Rama '{rule_id}' no encontrada"}
            rules[rule_id]["enabled"] = not rules[rule_id].get("enabled", True)
            save_pr_validation_rules(rules)
        elif rule_type == "custom":
            rules = load_custom_rules()
            if rule_id not in rules:
                return {"ok": False, "error": f"Regla '{rule_id}' no encontrada"}
            rules[rule_id]["enabled"] = not rules[rule_id].get("enabled", True)
            save_custom_rules(rules)
        else:
            return {"ok": False, "error": "Tipo de regla inválido"}
        
        logger.info(f"Regla {rule_type} '{rule_id}' toggled")
        return {"ok": True, "enabled": rules[rule_id]["enabled"]}
    except Exception as e:
        logger.error(f"Error toggling regla: {e}")
        return {"ok": False, "error": str(e)}
