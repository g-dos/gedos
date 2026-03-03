"""
GEDOS i18n — language-aware message strings for Telegram bot.
"""

_LANGS = ("en", "pt", "es")

_T: dict[str, dict[str, str]] = {
    "rate_limit": {"en": "⚠️ Rate limit exceeded. Max 10 commands per minute.", "pt": "⚠️ Limite excedido. Máx. 10 comandos por minuto.", "es": "⚠️ Límite excedido. Máx. 10 comandos por minuto."},
    "task_cancelled": {"en": "⚠️ Task cancelled.", "pt": "⚠️ Tarefa cancelada.", "es": "⚠️ Tarea cancelada."},
    "task_cancelled_at_step": {"en": "⚠️ Task cancelled at step {n}/{t}.", "pt": "⚠️ Tarefa cancelada no passo {n}/{t}.", "es": "⚠️ Tarea cancelada en el paso {n}/{t}."},
    "task_cancelled_user": {"en": "⚠️ Task cancelled by user at step {n}/{t}.", "pt": "⚠️ Tarefa cancelada pelo usuário no passo {n}/{t}.", "es": "⚠️ Tarea cancelada por el usuario en el paso {n}/{t}."},
    "task_cancelled_request": {"en": "⚠️ Task cancellation requested. Will stop at the next checkpoint.", "pt": "⚠️ Cancelamento solicitado. Vou parar no próximo ponto seguro.", "es": "⚠️ Cancelación solicitada. Me detendré en el próximo punto seguro."},
    "no_task_running": {"en": "No task running.", "pt": "Nenhuma tarefa em execução.", "es": "No hay tarea en ejecución."},
    "usage_task": {"en": "Usage: /task <task description>", "pt": "Uso: /task <descrição da tarefa>", "es": "Uso: /task <descripción de la tarea>"},
    "usage_ask": {"en": "Usage: /ask <question>", "pt": "Uso: /ask <pergunta>", "es": "Uso: /ask <pregunta>"},
    "usage_web": {"en": "Usage: /web <url>", "pt": "Uso: /web <url>", "es": "Uso: /web <url>"},
    "planning": {"en": "⚙️ Planning task...", "pt": "⚙️ Planejando tarefa...", "es": "⚙️ Planificando tarea..."},
    "planning_complete": {"en": "⚙️ Planning complete! {n} steps identified. Starting execution...", "pt": "⚙️ Planejamento concluído! {n} passos identificados. Iniciando...", "es": "⚙️ Planificación completa. {n} pasos identificados. Iniciando..."},
    "step_in_progress": {"en": "🔄 Step {n}/{t}: {step}", "pt": "🔄 Passo {n}/{t}: {step}", "es": "🔄 Paso {n}/{t}: {step}"},
    "step_retry": {"en": "⚠️ Step {n}/{t} failed. Retrying...", "pt": "⚠️ Passo {n}/{t} falhou. Tentando novamente...", "es": "⚠️ Paso {n}/{t} falló. Reintentando..."},
    "step_failed_continue": {"en": "❌ Step {n} failed: {err}\n\nContinue anyway? /yes /no", "pt": "❌ Passo {n} falhou: {err}\n\nContinuar mesmo assim? /yes /no", "es": "❌ Paso {n} falló: {err}\n\n¿Continuar de todos modos? /yes /no"},
    "step_success": {"en": "✅ Step {n}/{t}: {result}", "pt": "✅ Passo {n}/{t}: {result}", "es": "✅ Paso {n}/{t}: {result}"},
    "task_completed": {"en": "📋 Multi-step task completed!", "pt": "📋 Tarefa multi-etapa concluída!", "es": "📋 Tarea de varios pasos completada."},
    "task_finished_errors": {"en": "📋 Multi-step task finished with errors!", "pt": "📋 Tarefa multi-etapa finalizada com erros!", "es": "📋 Tarea de varios pasos finalizada con errores."},
    "task_summary_counts": {"en": "Steps: {success} successful, {failed} failed", "pt": "Passos: {success} concluídos, {failed} com falha", "es": "Pasos: {success} correctos, {failed} con fallo"},
    "task_summary_success": {"en": "Step {n}: ✅ {result}", "pt": "Passo {n}: ✅ {result}", "es": "Paso {n}: ✅ {result}"},
    "task_summary_failure": {"en": "Step {n}: ❌ {result}", "pt": "Passo {n}: ❌ {result}", "es": "Paso {n}: ❌ {result}"},
    "decision_timeout": {"en": "Decision timeout. Continuing with a failed step.", "pt": "Tempo de decisão esgotado. Continuando com o passo falho.", "es": "Se agotó el tiempo de decisión. Continuando con el paso fallido."},
    "multi_step_execution_error": {"en": "Multi-step execution error: {err}", "pt": "Erro na execução multi-etapa: {err}", "es": "Error en la ejecución de varios pasos: {err}"},
    "multi_step_planning_error": {"en": "Multi-step planning error: {err}", "pt": "Erro no planejamento multi-etapa: {err}", "es": "Error en la planificación de varios pasos: {err}"},
    "execution_error": {"en": "Execution error: {err}", "pt": "Erro de execução: {err}", "es": "Error de ejecución: {err}"},
    "no_result": {"en": "No result.", "pt": "Sem resultado.", "es": "Sin resultado."},
    "transcribing": {"en": "🎙️ Transcribing...", "pt": "🎙️ Transcrevendo...", "es": "🎙️ Transcribiendo..."},
    "voice_detected": {"en": "🎙️ Voice detected. Using {hint} as the transcription hint.", "pt": "🎙️ Voz detectada. Usando {hint} como dica para a transcrição.", "es": "🎙️ Voz detectada. Usando {hint} como pista para la transcripción."},
    "heard_executing": {"en": "🎙️ Heard: \"{text}\" — executing...", "pt": "🎙️ Ouvi: \"{text}\" — executando...", "es": "🎙️ Escuché: \"{text}\" — ejecutando..."},
    "transcription_failed": {"en": "❌ Transcription failed: {err}\n\nPlease type your command instead: /task <description>", "pt": "❌ Falha na transcrição: {err}\n\nDigite o comando: /task <descrição>", "es": "❌ Falló la transcripción: {err}\n\nEscriba el comando: /task <descripción>"},
    "voice_empty": {"en": "❌ Empty voice message. Please record again.", "pt": "❌ Mensagem de voz vazia. Grave novamente.", "es": "❌ Mensaje de voz vacío. Grabe de nuevo."},
    "voice_too_long": {"en": "❌ Voice message too long (max 60 seconds). Please send a shorter message.", "pt": "❌ Mensagem de voz muito longa (máx. 60 segundos). Envie uma mensagem mais curta.", "es": "❌ Mensaje de voz demasiado largo (máx. 60 segundos). Envíe uno más corto."},
    "voice_noise": {"en": "❌ Voice message contained only background noise.\n\nPlease speak clearly or type your command: /task <description>", "pt": "❌ A mensagem continha apenas ruído de fundo.\n\nFale claramente ou digite: /task <descrição>", "es": "❌ El mensaje contenía solo ruido de fondo.\n\nHable con claridad o escriba: /task <descripción>"},
    "voice_unclear": {"en": "❌ Could not understand the voice message (empty or unclear).\n\nPlease type your command instead: /task <description>", "pt": "❌ Não foi possível entender a mensagem de voz.\n\nDigite o comando: /task <descrição>", "es": "❌ No se pudo entender el mensaje de voz.\n\nEscriba el comando: /task <descripción>"},
    "scheduled_once": {"en": "✅ Scheduled: once at {time} — {task}", "pt": "✅ Agendado: uma vez às {time} — {task}", "es": "✅ Programado: una vez a las {time} — {task}"},
    "scheduled_daily": {"en": "✅ Scheduled: every day at {time} — {task}", "pt": "✅ Agendado: todos os dias às {time} — {task}", "es": "✅ Programado: todos los días a las {time} — {task}"},
    "scheduled_weekly": {"en": "✅ Scheduled: every {day} at {time} — {task}", "pt": "✅ Agendado: toda {day} às {time} — {task}", "es": "✅ Programado: cada {day} a las {time} — {task}"},
    "schedule_id_line": {"en": "Schedule ID: #{id}", "pt": "ID do agendamento: #{id}", "es": "ID de la programación: #{id}"},
    "schedule_invalid_format": {"en": "❌ Invalid format. Use:\n\n**Explicit:**\n• `daily 09:00 \"check HN\"`\n• `once 14:30 \"remind me\"`\n• `weekly monday 09:00 \"report\"`\n\n**Natural language:**\n• `every day at 9am \"check HN\"`\n• `tomorrow at 3pm \"remind me\"`\n• `every monday at 9am \"report\"`", "pt": "❌ Formato inválido. Use:\n\n**Explícito:**\n• `daily 09:00 \"check HN\"`\n• `once 14:30 \"me lembre\"`\n• `weekly monday 09:00 \"relatório\"`\n\n**Linguagem natural:**\n• `every day at 9am \"check HN\"`\n• `tomorrow at 3pm \"me lembre\"`\n• `every monday at 9am \"relatório\"`", "es": "❌ Formato inválido. Use:\n\n**Explícito:**\n• `daily 09:00 \"check HN\"`\n• `once 14:30 \"recuérdame\"`\n• `weekly monday 09:00 \"informe\"`\n\n**Lenguaje natural:**\n• `every day at 9am \"check HN\"`\n• `tomorrow at 3pm \"recuérdame\"`\n• `every monday at 9am \"informe\"`"},
    "schedule_create_failed": {"en": "❌ Failed to create schedule: {err}", "pt": "❌ Falha ao criar o agendamento: {err}", "es": "❌ No se pudo crear la programación: {err}"},
    "schedule_list_failed": {"en": "❌ Failed to list schedules: {err}", "pt": "❌ Falha ao listar os agendamentos: {err}", "es": "❌ No se pudieron listar las programaciones: {err}"},
    "no_schedules": {"en": "📅 No active schedules.", "pt": "📅 Nenhum agendamento ativo.", "es": "📅 No hay programaciones activas."},
    "schedules_title": {"en": "📅 Your Schedules", "pt": "📅 Seus Agendamentos", "es": "📅 Tus Programaciones"},
    "schedules_col_id": {"en": "ID", "pt": "ID", "es": "ID"},
    "schedules_col_when": {"en": "When", "pt": "Quando", "es": "Cuándo"},
    "schedules_col_task": {"en": "Task", "pt": "Tarefa", "es": "Tarea"},
    "schedules_col_last_run": {"en": "Last run", "pt": "Última execução", "es": "Última ejecución"},
    "schedule_when_daily": {"en": "Daily @ {time}", "pt": "Diário às {time}", "es": "Diario a las {time}"},
    "schedule_when_weekly": {"en": "{day} @ {time}", "pt": "{day} às {time}", "es": "{day} a las {time}"},
    "schedule_when_once": {"en": "Once @ {time}", "pt": "Uma vez às {time}", "es": "Una vez a las {time}"},
    "schedules_remove_hint": {"en": "Use /unschedule <id> to remove.", "pt": "Use /unschedule <id> para remover.", "es": "Use /unschedule <id> para eliminar."},
    "schedule_removed": {"en": "✅ Removed schedule #{id}: {task}", "pt": "✅ Agendamento #{id} removido: {task}", "es": "✅ Programación #{id} eliminada: {task}"},
    "schedule_usage_unschedule": {"en": "❌ Usage: `/unschedule <id>`\nExample: `/unschedule 5`", "pt": "❌ Uso: `/unschedule <id>`\nExemplo: `/unschedule 5`", "es": "❌ Uso: `/unschedule <id>`\nEjemplo: `/unschedule 5`"},
    "schedule_invalid_id": {"en": "❌ Invalid ID. Use a number like `/unschedule 5`", "pt": "❌ ID inválido. Use um número como `/unschedule 5`", "es": "❌ ID inválido. Use un número como `/unschedule 5`"},
    "schedule_not_found": {"en": "❌ Schedule #{id} not found.", "pt": "❌ Agendamento #{id} não encontrado.", "es": "❌ Programación #{id} no encontrada."},
    "schedule_not_owner": {"en": "❌ You can only unschedule your own tasks.", "pt": "❌ Você só pode remover seus próprios agendamentos.", "es": "❌ Solo puede eliminar sus propias programaciones."},
    "schedule_remove_failed": {"en": "❌ Failed to remove schedule #{id}", "pt": "❌ Falha ao remover o agendamento #{id}", "es": "❌ No se pudo eliminar la programación #{id}"},
    "unschedule_failed": {"en": "❌ Failed to unschedule: {err}", "pt": "❌ Falha ao remover o agendamento: {err}", "es": "❌ No se pudo desprogramar: {err}"},
    "scheduled_task_completed": {"en": "✅ Scheduled task completed:\n{task}\n\nResult: {result}", "pt": "✅ Tarefa agendada concluída:\n{task}\n\nResultado: {result}", "es": "✅ Tarea programada completada:\n{task}\n\nResultado: {result}"},
    "scheduled_task_failed": {"en": "❌ Scheduled task failed:\n{task}\n\nError: {result}", "pt": "❌ A tarefa agendada falhou:\n{task}\n\nErro: {result}", "es": "❌ La tarea programada falló:\n{task}\n\nError: {result}"},
    "scheduled_task_execution_failed": {"en": "Execution failed: {err}", "pt": "Falha na execução: {err}", "es": "Falló la ejecución: {err}"},
    "internal_error": {"en": "An internal error occurred. Please try again.", "pt": "Ocorreu um erro interno. Tente novamente.", "es": "Ocurrió un error interno. Intente de nuevo."},
    "pong": {"en": "pong\nMCP: available (run with --mcp)", "pt": "pong\nMCP: disponível (execute com --mcp)", "es": "pong\nMCP: disponible (ejecute con --mcp)"},
    "task_started": {"en": "⏳ Task started, executing...", "pt": "⏳ Tarefa iniciada, executando...", "es": "⏳ Tarea iniciada, ejecutando..."},
    "no_pending_decision": {"en": "No pending decision. Use this after a step fails.", "pt": "Nenhuma decisão pendente. Use isto depois que um passo falhar.", "es": "No hay una decisión pendiente. Use esto después de que falle un paso."},
    "cannot_identify_user": {"en": "⚠️ Cannot identify user.", "pt": "⚠️ Não foi possível identificar o usuário.", "es": "⚠️ No se puede identificar al usuario."},
    "ax_error": {"en": "Error: {err}", "pt": "Erro: {err}", "es": "Error: {err}"},
    "ax_app": {"en": "App: {app}", "pt": "App: {app}", "es": "App: {app}"},
    "ax_window": {"en": "  Window: {title}", "pt": "  Janela: {title}", "es": "  Ventana: {title}"},
    "ax_buttons": {"en": "Buttons: {buttons}", "pt": "Botões: {buttons}", "es": "Botones: {buttons}"},
    "untitled": {"en": "(untitled)", "pt": "(sem título)", "es": "(sin título)"},
    "no_output": {"en": "(no output)", "pt": "(sem saída)", "es": "(sin salida)"},
    "truncated_suffix": {"en": "\n... (truncated)", "pt": "\n... (truncado)", "es": "\n... (truncado)"},
    "generic_completed": {"en": "Completed", "pt": "Concluído", "es": "Completado"},
    "unknown_error": {"en": "Unknown error", "pt": "Erro desconhecido", "es": "Error desconocido"},
    "terminal_success": {"en": "✅ {command}\n\n{output}", "pt": "✅ {command}\n\n{output}", "es": "✅ {command}\n\n{output}"},
    "terminal_not_found": {"en": "❌ Command not found: {command}", "pt": "❌ Comando não encontrado: {command}", "es": "❌ Comando no encontrado: {command}"},
    "terminal_timeout": {"en": "⏱ {err}", "pt": "⏱ {err}", "es": "⏱ {err}"},
    "terminal_failure": {"en": "❌ {command} (code {code})\n\n{output}", "pt": "❌ {command} (código {code})\n\n{output}", "es": "❌ {command} (código {code})\n\n{output}"},
    "terminal_stderr": {"en": "\n\nstderr:\n{err}", "pt": "\n\nstderr:\n{err}", "es": "\n\nstderr:\n{err}"},
    "status_active": {"en": "Status: {status}\nTask: {task}{suffix}", "pt": "Status: {status}\nTarefa: {task}{suffix}", "es": "Estado: {status}\nTarea: {task}{suffix}"},
    "status_suffix": {"en": "...", "pt": "...", "es": "..."},
    "status_idle": {"en": "idle", "pt": "ociosa", "es": "inactiva"},
    "status_running": {"en": "running", "pt": "em execução", "es": "en ejecución"},
    "status_stopped": {"en": "stopped", "pt": "parada", "es": "detenida"},
    "clicked_button": {"en": "Clicked the button.", "pt": "Botão clicado.", "es": "Botón pulsado."},
    "button_not_found": {"en": "Button '{button}' not found.", "pt": "Botão '{button}' não encontrado.", "es": "Botón '{button}' no encontrado."},
    "start_first_time": {"en": "👋 Welcome to Gedos!\n\nI'm your autonomous AI agent for macOS. I can execute terminal commands, control your GUI, browse the web, and answer questions using a local LLM.\n\n**Choose your mode:**\n\n🤖 **Pilot Mode** — Fully autonomous. Send me a task, leave, and I'll execute and report back.\n   Example: `/task git status`\n\n👥 **Copilot Mode** — Proactive assistant. I monitor your screen and suggest actions in real time.\n   Enable with: `/copilot on`\n\n**Quick Start:**\n• `/task <description>` — Run any task\n• `/web <url>` — Browse the web\n• `/ask <question>` — Ask the LLM\n• `/help` — Full command list\n• `/ping` — Health check\n\nTry it now: `/task ls -la` or `/ask what is Python?`", "pt": "👋 Bem-vindo ao Gedos!\n\nSou seu agente autônomo para macOS. Posso executar comandos no terminal, controlar a interface, navegar na web e responder perguntas usando um LLM local.\n\n**Escolha seu modo:**\n\n🤖 **Modo Piloto** — Totalmente autônomo. Envie uma tarefa, saia e eu executo e reporto.\n   Exemplo: `/task git status`\n\n👥 **Modo Copilot** — Assistente proativo. Eu monitoro sua tela e sugiro ações em tempo real.\n   Ative com: `/copilot on`\n\n**Início rápido:**\n• `/task <description>` — Executa uma tarefa\n• `/web <url>` — Navega na web\n• `/ask <question>` — Pergunta ao LLM\n• `/help` — Lista completa de comandos\n• `/ping` — Health check\n\nTeste agora: `/task ls -la` ou `/ask o que é Python?`", "es": "👋 Bienvenido a Gedos.\n\nSoy tu agente autónomo para macOS. Puedo ejecutar comandos en la terminal, controlar la interfaz, navegar por la web y responder preguntas usando un LLM local.\n\n**Elija su modo:**\n\n🤖 **Modo Piloto** — Totalmente autónomo. Envíe una tarea, váyase y yo la ejecuto e informo.\n   Ejemplo: `/task git status`\n\n👥 **Modo Copilot** — Asistente proactivo. Monitoreo la pantalla y sugiero acciones en tiempo real.\n   Actívelo con: `/copilot on`\n\n**Inicio rápido:**\n• `/task <description>` — Ejecuta una tarea\n• `/web <url>` — Navega por la web\n• `/ask <question>` — Pregunta al LLM\n• `/help` — Lista completa de comandos\n• `/ping` — Verificación de salud\n\nPruebe ahora: `/task ls -la` o `/ask qué es Python?`"},
    "start_returning": {"en": "Hi, I'm Gedos. Your autonomous agent on Mac.\n\n**Pilot Mode** — Send a task and I'll execute it.\n**Copilot Mode** — `/copilot on` — proactive suggestions.\n\nCommands:\n- `/task <description>` — Run a task\n- `/status` — Task status\n- `/stop` — Stop execution\n- `/copilot on|off|status|sensitivity` — Copilot controls\n- `/memory` — Task history\n- `/web <url>` — Browse the web\n- `/ask <question>` — Ask the LLM\n- `/ping` — Health check\n- `/help` — List commands", "pt": "Olá, eu sou o Gedos. Seu agente autônomo no Mac.\n\n**Modo Piloto** — Envie uma tarefa e eu executo.\n**Modo Copilot** — `/copilot on` — sugestões proativas.\n\nComandos:\n- `/task <description>` — Executa uma tarefa\n- `/status` — Status da tarefa\n- `/stop` — Interrompe a execução\n- `/copilot on|off|status|sensitivity` — Controles do Copilot\n- `/memory` — Histórico de tarefas\n- `/web <url>` — Navega na web\n- `/ask <question>` — Pergunta ao LLM\n- `/ping` — Health check\n- `/help` — Lista de comandos", "es": "Hola, soy Gedos. Tu agente autónomo en Mac.\n\n**Modo Piloto** — Envíe una tarea y la ejecuto.\n**Modo Copilot** — `/copilot on` — sugerencias proactivas.\n\nComandos:\n- `/task <description>` — Ejecuta una tarea\n- `/status` — Estado de la tarea\n- `/stop` — Detiene la ejecución\n- `/copilot on|off|status|sensitivity` — Controles de Copilot\n- `/memory` — Historial de tareas\n- `/web <url>` — Navega por la web\n- `/ask <question>` — Pregunta al LLM\n- `/ping` — Verificación de salud\n- `/help` — Lista de comandos"},
    "help_copilot": {"en": "**Copilot Mode Active**\n\nI'm monitoring your screen and will send proactive suggestions and warnings.\n\n**Commands:**\n/copilot off — Disable Copilot\n/copilot status — Show Copilot state\n/copilot sensitivity high|medium|low — Adjust Copilot sensitivity\n/task <description> — Run a task manually\n/status — Current task status\n/stop — Stop a running task\n/memory — Task history\n/web <url> — Browse the web\n/ask <question> — Ask the LLM\n/schedule — Create scheduled tasks\n/schedules — List active schedules\n/unschedule <id> — Remove a schedule\n/ping — Health check\n\n**MCP Mode:**\nRun `python gedos.py --mcp` and connect from Claude Desktop or Cursor.\nSee `docs/mcp.md` for full setup.\n\n**How Copilot works:**\n• Watches the frontmost app context\n• Sends at most one suggestion per cooldown window\n• Warns if errors appear on screen", "pt": "**Modo Copilot Ativo**\n\nEstou monitorando sua tela e enviarei sugestões e alertas proativos.\n\n**Comandos:**\n/copilot off — Desativar o Copilot\n/copilot status — Mostrar o estado do Copilot\n/copilot sensitivity high|medium|low — Ajustar a sensibilidade\n/task <description> — Executar uma tarefa manualmente\n/status — Status atual da tarefa\n/stop — Parar a tarefa em execução\n/memory — Histórico de tarefas\n/web <url> — Navegar na web\n/ask <question> — Perguntar ao LLM\n/schedule — Criar agendamentos\n/schedules — Listar agendamentos ativos\n/unschedule <id> — Remover um agendamento\n/ping — Health check\n\n**Modo MCP:**\nExecute `python gedos.py --mcp` e conecte pelo Claude Desktop ou Cursor.\nVeja `docs/mcp.md` para a configuração completa.\n\n**Como o Copilot funciona:**\n• Observa o contexto do app em foco\n• Envia no máximo uma sugestão por janela de tempo\n• Avisa se erros aparecerem na tela", "es": "**Modo Copilot Activo**\n\nEstoy monitoreando la pantalla y enviaré sugerencias y alertas proactivos.\n\n**Comandos:**\n/copilot off — Desactivar Copilot\n/copilot status — Mostrar el estado de Copilot\n/copilot sensitivity high|medium|low — Ajustar la sensibilidad\n/task <description> — Ejecutar una tarea manualmente\n/status — Estado actual de la tarea\n/stop — Detener la tarea en ejecución\n/memory — Historial de tareas\n/web <url> — Navegar por la web\n/ask <question> — Preguntar al LLM\n/schedule — Crear programaciones\n/schedules — Listar programaciones activas\n/unschedule <id> — Eliminar una programación\n/ping — Verificación de salud\n\n**Modo MCP:**\nEjecute `python gedos.py --mcp` y conéctese desde Claude Desktop o Cursor.\nVea `docs/mcp.md` para la configuración completa.\n\n**Cómo funciona Copilot:**\n• Observa el contexto de la app activa\n• Envía como máximo una sugerencia por ventana de tiempo\n• Advierte si aparecen errores en la pantalla"},
    "help_pilot": {"en": "**Pilot Mode**\n\nSend me tasks and I'll execute them autonomously.\n\n**Commands:**\n/start — Welcome message\n/task <description> — Run a task\n/status — Current task status\n/stop — Stop a running task\n/copilot on — Enable Copilot Mode\n/memory — Task history\n/web <url> — Browse the web\n/ask <question> — Ask the LLM\n/schedule — Create scheduled tasks\n/schedules — List active schedules\n/unschedule <id> — Remove a schedule\n/ping — Health check\n\n**MCP Mode:**\nRun `python gedos.py --mcp` and connect from Claude Desktop or Cursor.\nSee `docs/mcp.md` for full setup.\n\n**Examples:**\n`/task ls -la`\n`/task git status`\n`/task navigate to google.com`\n`/ask what is Python?`\n`/schedule daily 09:00 \"check HN and summarize\"`\n`/schedule weekly monday 14:00 \"backup files\"`\n\nEnable Copilot for real-time assistance: `/copilot on`", "pt": "**Modo Piloto**\n\nEnvie tarefas e eu as executo de forma autônoma.\n\n**Comandos:**\n/start — Mensagem de boas-vindas\n/task <description> — Executa uma tarefa\n/status — Status atual da tarefa\n/stop — Para a tarefa em execução\n/copilot on — Ativa o Modo Copilot\n/memory — Histórico de tarefas\n/web <url> — Navega na web\n/ask <question> — Pergunta ao LLM\n/schedule — Cria agendamentos\n/schedules — Lista agendamentos ativos\n/unschedule <id> — Remove um agendamento\n/ping — Health check\n\n**Modo MCP:**\nExecute `python gedos.py --mcp` e conecte pelo Claude Desktop ou Cursor.\nVeja `docs/mcp.md` para a configuração completa.\n\n**Exemplos:**\n`/task ls -la`\n`/task git status`\n`/task navigate to google.com`\n`/ask o que é Python?`\n`/schedule daily 09:00 \"check HN and summarize\"`\n`/schedule weekly monday 14:00 \"backup files\"`\n\nAtive o Copilot para assistência em tempo real: `/copilot on`", "es": "**Modo Piloto**\n\nEnvíeme tareas y las ejecutaré de forma autónoma.\n\n**Comandos:**\n/start — Mensaje de bienvenida\n/task <description> — Ejecuta una tarea\n/status — Estado actual de la tarea\n/stop — Detiene la tarea en ejecución\n/copilot on — Activa el Modo Copilot\n/memory — Historial de tareas\n/web <url> — Navega por la web\n/ask <question> — Pregunta al LLM\n/schedule — Crea programaciones\n/schedules — Lista programaciones activas\n/unschedule <id> — Elimina una programación\n/ping — Verificación de salud\n\n**Modo MCP:**\nEjecute `python gedos.py --mcp` y conéctese desde Claude Desktop o Cursor.\nVea `docs/mcp.md` para la configuración completa.\n\n**Ejemplos:**\n`/task ls -la`\n`/task git status`\n`/task navigate to google.com`\n`/ask qué es Python?`\n`/schedule daily 09:00 \"check HN and summarize\"`\n`/schedule weekly monday 14:00 \"backup files\"`\n\nActive Copilot para asistencia en tiempo real: `/copilot on`"},
    "copilot_off": {"en": "Copilot Mode off.", "pt": "Modo Copilot desligado.", "es": "Modo Copilot desactivado."},
    "copilot_on": {"en": "Copilot Mode on. I'll monitor context and suggest when relevant.", "pt": "Modo Copilot ligado. Vou monitorar o contexto e sugerir quando fizer sentido.", "es": "Modo Copilot activado. Vigilaré el contexto y sugeriré cuando sea útil."},
    "copilot_status": {"en": "Copilot status\nActive: {active}\nSensitivity: {sensitivity}\nLast suggestion: {last}", "pt": "Status do Copilot\nAtivo: {active}\nSensibilidade: {sensitivity}\nÚltima sugestão: {last}", "es": "Estado de Copilot\nActivo: {active}\nSensibilidad: {sensitivity}\nÚltima sugerencia: {last}"},
    "copilot_state_active": {"en": "yes", "pt": "sim", "es": "sí"},
    "copilot_state_inactive": {"en": "no", "pt": "não", "es": "no"},
    "copilot_last_never": {"en": "never", "pt": "nunca", "es": "nunca"},
    "copilot_last_seconds_ago": {"en": "{seconds}s ago", "pt": "há {seconds}s", "es": "hace {seconds}s"},
    "copilot_sensitivity_high": {"en": "high", "pt": "alta", "es": "alta"},
    "copilot_sensitivity_medium": {"en": "medium", "pt": "média", "es": "media"},
    "copilot_sensitivity_low": {"en": "low", "pt": "baixa", "es": "baja"},
    "copilot_sensitivity_set": {"en": "Copilot sensitivity set to {sensitivity}.", "pt": "Sensibilidade do Copilot definida como {sensitivity}.", "es": "La sensibilidad de Copilot se ajustó a {sensitivity}."},
    "copilot_sensitivity_usage": {"en": "Usage: /copilot sensitivity high|medium|low", "pt": "Uso: /copilot sensitivity high|medium|low", "es": "Uso: /copilot sensitivity high|medium|low"},
    "copilot_hint_terminal_error": {"en": "I see an error. Want me to fix it?", "pt": "Vejo um erro. Quer que eu corrija?", "es": "Veo un error. ¿Quiere que lo corrija?"},
    "copilot_hint_terminal": {"en": "Want me to run a command in Terminal?", "pt": "Quer que eu execute um comando no Terminal?", "es": "¿Quiere que ejecute un comando en Terminal?"},
    "copilot_hint_vscode": {"en": "Want me to run tests, check git status, or look at errors?", "pt": "Quer que eu rode os testes, veja o git status ou confira os erros?", "es": "¿Quiere que ejecute pruebas, revise git status o vea los errores?"},
    "copilot_hint_github_pr": {"en": "Want me to summarize this PR?", "pt": "Quer que eu resuma este PR?", "es": "¿Quiere que resuma este PR?"},
    "copilot_hint_browser": {"en": "Want me to search or open a page?", "pt": "Quer que eu pesquise ou abra uma página?", "es": "¿Quiere que busque o abra una página?"},
    "copilot_hint_finder": {"en": "Want me to organize these files?", "pt": "Quer que eu organize esses arquivos?", "es": "¿Quiere que organice estos archivos?"},
    "copilot_hint_idle": {"en": "You seem idle. Want me to handle anything?", "pt": "Você parece ausente. Quer que eu cuide de algo?", "es": "Parece inactivo. ¿Quiere que me encargue de algo?"},
    "copilot_hint_generic": {"en": "You're in {app}. Want me to do something?", "pt": "Você está em {app}. Quer que eu faça algo?", "es": "Está en {app}. ¿Quiere que haga algo?"},
    "copilot_hint_warning_generic": {"en": "I spotted something that looks risky on screen. Want me to investigate?", "pt": "Vi algo arriscado na tela. Quer que eu investigue?", "es": "Vi algo riesgoso en la pantalla. ¿Quiere que lo investigue?"},
    "memory_empty": {"en": "No tasks in history.", "pt": "Nenhuma tarefa no histórico.", "es": "No hay tareas en el historial."},
    "memory_header": {"en": "Recent tasks:", "pt": "Tarefas recentes:", "es": "Tareas recientes:"},
    "memory_item": {"en": "- [{status}] {description}", "pt": "- [{status}] {description}", "es": "- [{status}] {description}"},
    "memory_item_truncated": {"en": "- [{status}] {description}...", "pt": "- [{status}] {description}...", "es": "- [{status}] {description}..."},
    "web_page_loaded": {"en": "Page loaded: {title}\n{url}", "pt": "Página carregada: {title}\n{url}", "es": "Página cargada: {title}\n{url}"},
    "web_error": {"en": "Error: {err}", "pt": "Erro: {err}", "es": "Error: {err}"},
}


def _ensure_complete_translations() -> None:
    """Fail fast if any i18n key is missing a supported language."""
    missing: list[str] = []
    for key, translations in _T.items():
        for lang in _LANGS:
            if lang not in translations:
                missing.append(f"{key}.{lang}")
    if missing:
        raise ValueError(f"Missing translations: {', '.join(sorted(missing))}")


_ensure_complete_translations()


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Get translated string. Falls back to English if key or lang missing."""
    if key not in _T:
        return key
    msg = _T[key].get(lang) or _T[key].get("en") or key
    for k, v in kwargs.items():
        msg = msg.replace("{" + k + "}", str(v))
    return msg
