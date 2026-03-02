"""
GEDOS i18n — language-aware message strings for Telegram bot.
"""

_T: dict[str, dict[str, str]] = {
    "rate_limit": {"en": "⚠️ Rate limit exceeded. Max 10 commands per minute.", "pt": "⚠️ Limite excedido. Máx. 10 comandos por minuto.", "es": "⚠️ Límite excedido. Máx. 10 comandos por minuto."},
    "task_cancelled": {"en": "⚠️ Task cancelled.", "pt": "⚠️ Tarefa cancelada.", "es": "⚠️ Tarea cancelada."},
    "no_task_running": {"en": "No task running.", "pt": "Nenhuma tarefa em execução.", "es": "No hay tarea en ejecución."},
    "usage_task": {"en": "Usage: /task <task description>", "pt": "Uso: /task <descrição da tarefa>", "es": "Uso: /task <descripción de la tarea>"},
    "usage_ask": {"en": "Usage: /ask <question>", "pt": "Uso: /ask <pergunta>", "es": "Uso: /ask <pregunta>"},
    "planning": {"en": "⚙️ Planning task...", "pt": "⚙️ Planejando tarefa...", "es": "⚙️ Planificando tarea..."},
    "planning_complete": {"en": "⚙️ Planning complete! {n} steps identified. Starting execution...", "pt": "⚙️ Planejamento concluído! {n} passos identificados. Iniciando...", "es": "⚙️ Planificación completa! {n} pasos identificados. Iniciando..."},
    "step_retry": {"en": "⚠️ Step {n}/{t} failed. Retrying...", "pt": "⚠️ Passo {n}/{t} falhou. Tentando novamente...", "es": "⚠️ Paso {n}/{t} falló. Reintentando..."},
    "step_failed_continue": {"en": "❌ Step {n} failed: {err}\n\nContinue anyway? /yes /no", "pt": "❌ Passo {n} falhou: {err}\n\nContinuar mesmo assim? /yes /no", "es": "❌ Paso {n} falló: {err}\n\n¿Continuar de todos modos? /yes /no"},
    "task_cancelled_user": {"en": "⚠️ Task cancelled by user at step {n}/{t}.", "pt": "⚠️ Tarefa cancelada pelo usuário no passo {n}/{t}.", "es": "⚠️ Tarea cancelada por el usuario en el paso {n}/{t}."},
    "task_completed": {"en": "📋 Multi-step task completed!", "pt": "📋 Tarefa multi-etapa concluída!", "es": "📋 ¡Tarea multi-paso completada!"},
    "task_finished_errors": {"en": "📋 Multi-step task finished with errors!", "pt": "📋 Tarefa multi-etapa finalizada com erros!", "es": "📋 ¡Tarea multi-paso finalizada con errores!"},
    "transcribing": {"en": "🎙️ Transcribing...", "pt": "🎙️ Transcrevendo...", "es": "🎙️ Transcribiendo..."},
    "heard_executing": {"en": "🎙️ Heard: \"{text}\" — executing...", "pt": "🎙️ Ouvi: \"{text}\" — executando...", "es": "🎙️ Escuché: \"{text}\" — ejecutando..."},
    "transcription_failed": {"en": "❌ Transcription failed: {err}\n\nPlease type your command instead: /task <description>", "pt": "❌ Falha na transcrição: {err}\n\nDigite o comando: /task <descrição>", "es": "❌ Error de transcripción: {err}\n\nEscriba el comando: /task <descripción>"},
    "voice_empty": {"en": "❌ Empty voice message. Please record again.", "pt": "❌ Mensagem de voz vazia. Grave novamente.", "es": "❌ Mensaje de voz vacío. Grabe de nuevo."},
    "voice_too_long": {"en": "❌ Voice message too long (max 60 seconds). Please send a shorter message.", "pt": "❌ Mensagem de voz muito longa (máx. 60 segundos). Envie uma mensagem mais curta.", "es": "❌ Mensaje de voz muy largo (máx. 60 segundos). Envíe un mensaje más corto."},
    "voice_noise": {"en": "❌ Voice message contained only background noise.\n\nPlease speak clearly or type your command: /task <description>", "pt": "❌ A mensagem continha apenas ruído de fundo.\n\nFale claramente ou digite: /task <descrição>", "es": "❌ El mensaje contenía solo ruido de fondo.\n\nHable claramente o escriba: /task <descripción>"},
    "voice_unclear": {"en": "❌ Could not understand the voice message (empty or unclear).\n\nPlease type your command instead: /task <description>", "pt": "❌ Não foi possível entender a mensagem de voz.\n\nDigite o comando: /task <descrição>", "es": "❌ No se pudo entender el mensaje de voz.\n\nEscriba el comando: /task <descripción>"},
    "scheduled_once": {"en": "✅ Scheduled: once at {time} — {task}", "pt": "✅ Agendado: uma vez às {time} — {task}", "es": "✅ Programado: una vez a las {time} — {task}"},
    "scheduled_daily": {"en": "✅ Scheduled: every day at {time} — {task}", "pt": "✅ Agendado: todo dia às {time} — {task}", "es": "✅ Programado: cada día a las {time} — {task}"},
    "scheduled_weekly": {"en": "✅ Scheduled: every {day} at {time} — {task}", "pt": "✅ Agendado: toda {day} às {time} — {task}", "es": "✅ Programado: cada {day} a las {time} — {task}"},
    "no_schedules": {"en": "📅 No active schedules.", "pt": "📅 Nenhum agendamento ativo.", "es": "📅 No hay programaciones activas."},
    "schedule_removed": {"en": "✅ Removed schedule #{id}: {task}", "pt": "✅ Agendamento #{id} removido: {task}", "es": "✅ Programación #{id} eliminada: {task}"},
    "internal_error": {"en": "An internal error occurred. Please try again.", "pt": "Ocorreu um erro interno. Tente novamente.", "es": "Ocurrió un error interno. Intente de nuevo."},
    "pong": {"en": "pong", "pt": "pong", "es": "pong"},
    "task_started": {"en": "⏳ Task started, executing...", "pt": "⏳ Tarefa iniciada, executando...", "es": "⏳ Tarea iniciada, ejecutando..."},
    "no_pending_decision": {"en": "No pending decision. Use this after a step fails.", "pt": "Nenhuma decisão pendente. Use após uma falha de passo.", "es": "No hay decisión pendiente. Use después de que falle un paso."},
    "cannot_identify_user": {"en": "⚠️ Cannot identify user.", "pt": "⚠️ Não foi possível identificar o usuário.", "es": "⚠️ No se puede identificar al usuario."},
}


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Get translated string. Falls back to English if key or lang missing."""
    if key not in _T:
        return key
    msg = _T[key].get(lang) or _T[key].get("en") or key
    for k, v in kwargs.items():
        msg = msg.replace("{" + k + "}", str(v))
    return msg
