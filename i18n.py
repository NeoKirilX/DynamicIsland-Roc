#!/usr/bin/env python3

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

LANGUAGES: dict[str, str] = {
    "ru": "Русский",
    "en": "English",
    "es": "Español",
    "de": "Deutsch",
    "fr": "Français",
    "it": "Italiano",
    "pt": "Português",
    "zh": "中文",
    "ja": "日本語",
    "uk": "Українська",
}

LANGUAGE_KEYS: list[str] = list(LANGUAGES.keys())

TRANSLATIONS: dict[str, dict[str, str]] = {
    # Headers
    "settings_title": {
        "ru": "НАСТРОЙКИ", "en": "SETTINGS", "es": "CONFIGURACIÓN", "de": "EINSTELLUNGEN",
        "fr": "PARAMÈTRES", "it": "IMPOSTAZIONI", "pt": "CONFIGURAÇÕES", "zh": "设置", "ja": "設定", "uk": "НАЛАШТУВАННЯ"
    },
    "menu_title": {
        "ru": "DYNAMIC ISLAND", "en": "DYNAMIC ISLAND", "es": "DYNAMIC ISLAND", "de": "DYNAMIC ISLAND",
        "fr": "DYNAMIC ISLAND", "it": "DYNAMIC ISLAND", "pt": "DYNAMIC ISLAND", "zh": "DYNAMIC ISLAND", "ja": "DYNAMIC ISLAND", "uk": "DYNAMIC ISLAND"
    },
    "look_title": {
        "ru": "ОФОРМЛЕНИЕ", "en": "APPEARANCE", "es": "APARIENCIA", "de": "AUSSEHEN",
        "fr": "APPARENCE", "it": "ASPETTO", "pt": "APARÊNCIA", "zh": "外观", "ja": "外観", "uk": "ОФОРМЛЕННЯ"
    },
    "equalizer_title": {
        "ru": "ЭКВАЛАЙЗЕР", "en": "EQUALIZER", "es": "ECUALIZADOR", "de": "EQUALIZER",
        "fr": "ÉGALISEUR", "it": "EQUALIZZATORE", "pt": "EQUALIZADOR", "zh": "均衡器", "ja": "イコライザー", "uk": "ЕКВАЛАЙЗЕР"
    },
    "text_anim_title": {
        "ru": "АНИМАЦИЯ ТЕКСТА", "en": "TEXT ANIMATION", "es": "ANIMACIÓN DE TEXTO", "de": "TEXTANIMATION",
        "fr": "ANIMATION DU TEXTE", "it": "ANIMAZIONE TESTO", "pt": "ANIMAÇÃO DE TEXTO", "zh": "文本动画", "ja": "テキストアニメーション", "uk": "АНІМАЦІЯ ТЕКСТУ"
    },
    "combo_title": {
        "ru": "КОМБО ПОВТОРОВ", "en": "REPEAT COMBO", "es": "COMBO DE REPETICIONES", "de": "WIEDERHOLUNGS-COMBO",
        "fr": "COMBO DE RÉPÉTITIONS", "it": "COMBO DI RIPETIZIONI", "pt": "COMBO DE REPETIÇÕES", "zh": "重复连击", "ja": "リピートコンボ", "uk": "КОМБО ПОВТОРІВ"
    },
    "shelf_title": {
        "ru": "ПОЛКА", "en": "SHELF", "es": "ESTANTE", "de": "ABLAGE",
        "fr": "ÉTAGÈRE", "it": "SCAFFALE", "pt": "PRATELEIRA", "zh": "搁板", "ja": "シェルフ", "uk": "ПОЛИЦЯ"
    },
    "timer_title": {
        "ru": "ТАЙМЕР", "en": "TIMER", "es": "TEMPORIZADOR", "de": "TIMER",
        "fr": "MINUTEUR", "it": "TIMER", "pt": "TEMPORIZADOR", "zh": "计时器", "ja": "タイマー", "uk": "ТАЙМЕР"
    },
    "update_title": {
        "ru": "ОБНОВЛЕНИЕ", "en": "UPDATE", "es": "ACTUALIZACIÓN", "de": "AKTUALISIERUNG",
        "fr": "MISE À JOUR", "it": "AGGIORNAMENTO", "pt": "ATUALIZAÇÃO", "zh": "更新", "ja": "アップデート", "uk": "ОНОВЛЕННЯ"
    },

    # Settings Rows
    "lyrics": {
        "ru": "Текст песен", "en": "Song lyrics", "es": "Letras de canciones", "de": "Songtexte",
        "fr": "Paroles de chansons", "it": "Testi delle canzoni", "pt": "Letras das músicas", "zh": "歌词显示", "ja": "歌詞表示", "uk": "Текст пісень"
    },
    "lyric_effects": {
        "ru": "Эффекты текста", "en": "Text effects", "es": "Efectos de texto", "de": "Texteffekte",
        "fr": "Effets de texte", "it": "Effetti di testo", "pt": "Efeitos de texto", "zh": "文字特效", "ja": "テキスト効果", "uk": "Ефекти тексту"
    },
    "rim": {
        "ru": "Ободок острова", "en": "Island rim", "es": "Borde de isla", "de": "Inselrand",
        "fr": "Bordure de l'île", "it": "Bordo isola", "pt": "Borda da ilha", "zh": "岛屿光环", "ja": "アイランドの縁", "uk": "Обід острова"
    },
    "shadow": {
        "ru": "Тень острова", "en": "Island shadow", "es": "Sombra de isla", "de": "Inselschatten",
        "fr": "Ombre de l'île", "it": "Ombra isola", "pt": "Sombra da ilha", "zh": "岛屿阴影", "ja": "アイランドの影", "uk": "Тінь острова"
    },
    "app_volume": {
        "ru": "Громкость приложения", "en": "App volume", "es": "Volumen de app", "de": "App-Lautstärke",
        "fr": "Volume d'application", "it": "Volume applicazione", "pt": "Volume do aplicativo", "zh": "应用独立音量", "ja": "アプリ音量", "uk": "Гучність програми"
    },
    "network": {
        "ru": "Уведомления о сети", "en": "Network alerts", "es": "Alertas de red", "de": "Netzwerkbenachrichtigungen",
        "fr": "Alertes réseau", "it": "Avvisi di rete", "pt": "Alertas de rede", "zh": "网络状态提示", "ja": "ネットワーク通知", "uk": "Сповіщення про мережу"
    },
    "weather": {
        "ru": "Виджет погоды", "en": "Weather widget", "es": "Widget de clima", "de": "Wetter-Widget",
        "fr": "Widget météo", "it": "Widget meteo", "pt": "Widget de clima", "zh": "天气小部件", "ja": "天気ウィジェット", "uk": "Віджет погоди"
    },
    "system_stats": {
        "ru": "Мониторинг системы", "en": "System stats", "es": "Monitoreo del sistema", "de": "Systemüberwachung",
        "fr": "Surveillance système", "it": "Monitoraggio sistema", "pt": "Monitoramento do sistema", "zh": "系统资源监控", "ja": "システム監視", "uk": "Моніторинг системи"
    },
    "hide_fullscreen": {
        "ru": "Скрывать на полном экране", "en": "Hide on fullscreen", "es": "Ocultar en pantalla completa", "de": "Im Vollbild verbergen",
        "fr": "Masquer en plein écran", "it": "Nascondi a schermo intero", "pt": "Ocultar em tela cheia", "zh": "全屏时自动隐藏", "ja": "全画面表示時に隠す", "uk": "Приховувати на повному екрані"
    },
    "click_lock": {
        "ru": "Задержка при анимации", "en": "Animation click delay", "es": "Retardo de animación", "de": "Animationsverzögerung",
        "fr": "Délai d'animation", "it": "Ritardo animazione", "pt": "Atraso de animação", "zh": "动画点击延迟", "ja": "アニメーション遅延", "uk": "Затримка при анімації"
    },
    "autostart": {
        "ru": "Запускать при старте", "en": "Run at startup", "es": "Iniciar al arrancar", "de": "Beim Start ausführen",
        "fr": "Lancer au démarrage", "it": "Esegui all'avvio", "pt": "Iniciar com o sistema", "zh": "开机自动启动", "ja": "システム起動時に実行", "uk": "Запускати при старті"
    },
    "capitalize_title": {
        "ru": "Заглавная буква в названии", "en": "Capitalize track title", "es": "Mayúscula en título", "de": "Titel großschreiben",
        "fr": "Majuscule au titre", "it": "Maiuscola nel titolo", "pt": "Maiúscula no título", "zh": "标题首字母大写", "ja": "タイトルを大文字化", "uk": "Велика літера в назві"
    },
    "language": {
        "ru": "Язык интерфейса", "en": "Interface language", "es": "Idioma de interfaz", "de": "Sprache",
        "fr": "Langue d'interface", "it": "Lingua interfaccia", "pt": "Idioma da interface", "zh": "界面语言", "ja": "言語設定", "uk": "Мова інтерфейсу"
    },
    "export_config": {
        "ru": "Экспорт конфигурации", "en": "Export configuration", "es": "Exportar configuración", "de": "Konfiguration exportieren",
        "fr": "Exporter la configuration", "it": "Esporta configurazione", "pt": "Exportar configuração", "zh": "导出配置文件", "ja": "設定のエクスポート", "uk": "Експорт конфігурації"
    },
    "import_config": {
        "ru": "Импорт конфигурации", "en": "Import configuration", "es": "Importar configuración", "de": "Konfiguration importieren",
        "fr": "Importer la configuration", "it": "Importa configurazione", "pt": "Importar configuração", "zh": "导入配置文件", "ja": "設定のインポート", "uk": "Імпорт конфігурації"
    },
    "clear_cache": {
        "ru": "Очистить кэш", "en": "Clear cache", "es": "Limpiar caché", "de": "Cache leeren",
        "fr": "Vider le cache", "it": "Cancella cache", "pt": "Limpar cache", "zh": "清理本地缓存", "ja": "キャッシュをクリア", "uk": "Очистити кеш"
    },
    "cache_cleared": {
        "ru": "Очищено!", "en": "Cleared!", "es": "¡Limpiado!", "de": "Geleert!",
        "fr": "Nettoyé !", "it": "Svuotato!", "pt": "Limpo!", "zh": "已清理！", "ja": "クリア完了！", "uk": "Очищено!"
    },
    "update": {
        "ru": "Обновление", "en": "Update", "es": "Actualización", "de": "Aktualisierung",
        "fr": "Mise à jour", "it": "Aggiornamento", "pt": "Atualização", "zh": "软件更新", "ja": "アップデート", "uk": "Оновлення"
    },

    # Menu items
    "menu_player": {
        "ru": "Музыка", "en": "Music", "es": "Música", "de": "Musik",
        "fr": "Musique", "it": "Musica", "pt": "Música", "zh": "音乐播放器", "ja": "ミュージック", "uk": "Музика"
    },
    "menu_settings": {
        "ru": "Настройки", "en": "Settings", "es": "Configuración", "de": "Einstellungen",
        "fr": "Paramètres", "it": "Impostazioni", "pt": "Configurações", "zh": "岛屿设置", "ja": "設定", "uk": "Налаштування"
    },
    "menu_look": {
        "ru": "Оформление", "en": "Appearance", "es": "Apariencia", "de": "Aussehen",
        "fr": "Apparence", "it": "Aspetto", "pt": "Aparência", "zh": "外观样式", "ja": "外観スタイル", "uk": "Оформлення"
    },
    "menu_shelf": {
        "ru": "Полка", "en": "Shelf", "es": "Estante", "de": "Ablage",
        "fr": "Étagère", "it": "Scaffale", "pt": "Prateleira", "zh": "文件暂存", "ja": "シェルフ", "uk": "Полиця"
    },
    "menu_timer": {
        "ru": "Таймер", "en": "Timer", "es": "Temporizador", "de": "Timer",
        "fr": "Minuteur", "it": "Timer", "pt": "Temporizador", "zh": "专注计时", "ja": "タイマー", "uk": "Таймер"
    },
    "menu_power": {
        "ru": "Выйти", "en": "Quit", "es": "Salir", "de": "Beenden",
        "fr": "Quitter", "it": "Esci", "pt": "Sair", "zh": "退出程序", "ja": "終了", "uk": "Вийти"
    },

    # Appearance options
    "accent_color": {
        "ru": "Цвет акцента", "en": "Accent color", "es": "Color de acento", "de": "Akzentfarbe",
        "fr": "Couleur d'accent", "it": "Colore di accento", "pt": "Cor de destaque", "zh": "强调色彩", "ja": "アクセントカラー", "uk": "Колір акценту"
    },
    "material": {
        "ru": "Материал", "en": "Material", "es": "Material", "de": "Material",
        "fr": "Matériau", "it": "Materiale", "pt": "Material", "zh": "背景材质", "ja": "マテリアル", "uk": "Матеріал"
    },
    "alignment": {
        "ru": "Положение", "en": "Alignment", "es": "Alineación", "de": "Ausrichtung",
        "fr": "Alignement", "it": "Allineamento", "pt": "Alinhamento", "zh": "对齐方式", "ja": "配置位置", "uk": "Розташування"
    },
    "scale": {
        "ru": "Масштаб", "en": "Scale", "es": "Escala", "de": "Skalierung",
        "fr": "Échelle", "it": "Scala", "pt": "Escala", "zh": "整体缩放", "ja": "拡大率", "uk": "Масштаб"
    },
    "pos_x": {
        "ru": "Позиция X", "en": "Position X", "es": "Posición X", "de": "Position X",
        "fr": "Position X", "it": "Posizione X", "pt": "Posição X", "zh": "X 坐标", "ja": "X 位置", "uk": "Позиція X"
    },
    "pos_y": {
        "ru": "Позиция Y", "en": "Position Y", "es": "Posición Y", "de": "Position Y",
        "fr": "Position Y", "it": "Posizione Y", "pt": "Posição Y", "zh": "Y 坐标", "ja": "Y 位置", "uk": "Позиція Y"
    },
    "gap": {
        "ru": "Отступ сверху", "en": "Top gap", "es": "Espacio superior", "de": "Oberer Abstand",
        "fr": "Marge supérieure", "it": "Spazio superiore", "pt": "Espaço superior", "zh": "顶部边距", "ja": "上部余白", "uk": "Відступ зверху"
    },
    "radius": {
        "ru": "Скругление", "en": "Corner radius", "es": "Radio de esquina", "de": "Eckenradius",
        "fr": "Rayon des angles", "it": "Raggio angoli", "pt": "Raio dos cantos", "zh": "圆角弧度", "ja": "角丸半径", "uk": "Закруглення"
    },
    "glass": {
        "ru": "Непрозрачность", "en": "Opacity", "es": "Opacidad", "de": "Deckkraft",
        "fr": "Opacité", "it": "Opacità", "pt": "Opacidade", "zh": "不透明度", "ja": "不透明度", "uk": "Непрозорість"
    },
    "height_offset": {
        "ru": "Высота острова", "en": "Island height", "es": "Altura de isla", "de": "Inselhöhe",
        "fr": "Hauteur de l'île", "it": "Altezza isola", "pt": "Altura da ilha", "zh": "岛屿高度", "ja": "アイランド高さ", "uk": "Висота острова"
    },
    "text_scale": {
        "ru": "Размер текста", "en": "Text size", "es": "Tamaño de texto", "de": "Textgröße",
        "fr": "Taille du texte", "it": "Dimensione testo", "pt": "Tamanho do texto", "zh": "文字字号", "ja": "文字サイズ", "uk": "Розмір тексту"
    },
    "text_animation": {
        "ru": "Анимация текста", "en": "Text animation", "es": "Animación de texto", "de": "Textanimation",
        "fr": "Animation de texte", "it": "Animazione testo", "pt": "Animação de texto", "zh": "动态歌词设置", "ja": "テキストアニメ", "uk": "Анімація тексту"
    },

    # Combo
    "combo_enabled": {
        "ru": "Включить комбо", "en": "Enable combo", "es": "Activar combo", "de": "Combo aktivieren",
        "fr": "Activer le combo", "it": "Attiva combo", "pt": "Ativar combo", "zh": "开启连击效果", "ja": "コンボを有効化", "uk": "Увімкнути комбо"
    },
    "combo_repeats": {
        "ru": "Порог повторов", "en": "Repeat threshold", "es": "Umbral de repeticiones", "de": "Wiederholungsschwelle",
        "fr": "Seuil de répétitions", "it": "Soglia ripetizioni", "pt": "Limite de repetições", "zh": "触发重复次数", "ja": "リピート判定回数", "uk": "Поріг повторів"
    },
    "combo_style": {
        "ru": "Стиль счётчика", "en": "Counter style", "es": "Estilo del contador", "de": "Zählerstil",
        "fr": "Style du compteur", "it": "Stile contatore", "pt": "Estilo do contador", "zh": "连击数字样式", "ja": "カウンタースタイル", "uk": "Стиль лічильника"
    },
    "combo_split": {
        "ru": "Режим разбивки", "en": "Split mode", "es": "Modo de división", "de": "Teilungsmodus",
        "fr": "Mode de découpage", "it": "Modalità divisione", "pt": "Modo de divisão", "zh": "短语拆分规则", "ja": "分割モード", "uk": "Режим розбивки"
    },
    "combo_split_all": {
        "ru": "Все варианты", "en": "All variants", "es": "Todas las variantes", "de": "Alle Varianten",
        "fr": "Toutes variantes", "it": "Tutte le varianti", "pt": "Todas as variantes", "zh": "智能全部", "ja": "全パターン", "uk": "Усі варіанти"
    },
    "combo_split_punct": {
        "ru": "По знакам", "en": "By punctuation", "es": "Por puntuación", "de": "Nach Satzzeichen",
        "fr": "Par ponctuation", "it": "Per punteggiatura", "pt": "Por pontuação", "zh": "按标点符号", "ja": "句読点基準", "uk": "За розділовими знаками"
    },
    "combo_split_words": {
        "ru": "По словам", "en": "By words", "es": "Por palabras", "de": "Nach Wörtern",
        "fr": "Par mots", "it": "Per parole", "pt": "Por palavras", "zh": "按独立词语", "ja": "単語基準", "uk": "За словами"
    },
    "combo_split_lines": {
        "ru": "Только строки", "en": "Lines only", "es": "Solo líneas", "de": "Nur Zeilen",
        "fr": "Lignes seules", "it": "Solo righe", "pt": "Apenas linhas", "zh": "仅完整单行", "ja": "行単位のみ", "uk": "Лише рядки"
    },
    "combo_ignore_adlibs": {
        "ru": "Игнорировать эдлибы", "en": "Ignore ad-libs", "es": "Ignorar ad-libs", "de": "Ad-libs ignorieren",
        "fr": "Ignorer les ad-libs", "it": "Ignora ad-lib", "pt": "Ignorar ad-libs", "zh": "忽略和声伴唱", "ja": "合いの手を無視", "uk": "Ігнорувати едліби"
    },
    "combo_strip_brackets": {
        "ru": "Очищать скобки", "en": "Strip brackets", "es": "Quitar corchetes", "de": "Klammern säubern",
        "fr": "Nettoyer parenthèses", "it": "Pulisci parentesi", "pt": "Remover colchetes", "zh": "过滤括号文本", "ja": "括弧を除去", "uk": "Очищати дужки"
    },
    "combo_min_word_len": {
        "ru": "Минимум букв", "en": "Min word letters", "es": "Mínimo de letras", "de": "Min. Buchstaben",
        "fr": "Lettres min.", "it": "Lettere minime", "pt": "Mínimo de letras", "zh": "最短单词长度", "ja": "最小文字数", "uk": "Мінімум літер"
    },

    # Timer
    "timer_start": {
        "ru": "Запустить", "en": "Start", "es": "Iniciar", "de": "Starten",
        "fr": "Démarrer", "it": "Avvia", "pt": "Iniciar", "zh": "开始计时", "ja": "スタート", "uk": "Запустити"
    },
    "timer_paused": {
        "ru": "На паузе", "en": "Paused", "es": "En pausa", "de": "Pausiert",
        "fr": "En pause", "it": "In pausa", "pt": "Em pausa", "zh": "暂停中", "ja": "一時停止", "uk": "На паузі"
    },
    "timer_counting": {
        "ru": "Идёт отсчёт", "en": "Running", "es": "En curso", "de": "Läuft",
        "fr": "En cours", "it": "In corso", "pt": "Contando", "zh": "进行中", "ja": "カウント中", "uk": "Йде відлік"
    },
    "timer_finishing": {
        "ru": "Завершается!", "en": "Finishing!", "es": "¡Finalizando!", "de": "Endet!",
        "fr": "Bientôt fini !", "it": "In conclusione!", "pt": "Finalizando!", "zh": "即将完成！", "ja": "まもなく終了！", "uk": "Завершується!"
    },

    # Shelf
    "shelf_clear": {
        "ru": "Очистить", "en": "Clear", "es": "Limpiar", "de": "Leeren",
        "fr": "Effacer", "it": "Cancella", "pt": "Limpar", "zh": "清空", "ja": "クリア", "uk": "Очистити"
    },
    "shelf_empty": {
        "ru": "Полка пуста", "en": "Shelf is empty", "es": "El estante está vacío", "de": "Ablage ist leer",
        "fr": "L'étagère est vide", "it": "Lo scaffale è vuoto", "pt": "A prateleira está vazia", "zh": "暂存区为空", "ja": "シェルフは空です", "uk": "Полиця порожня"
    },
    "config_applied": {
        "ru": "Конфиг применён", "en": "Config applied", "es": "Configuración aplicada", "de": "Konfiguration angewendet",
        "fr": "Configuration appliquée", "it": "Configurazione applicata", "pt": "Configuração aplicada", "zh": "配置已成功应用", "ja": "設定が適用されました", "uk": "Конфіг застосовано"
    },
    "config_error": {
        "ru": "Ошибка конфига", "en": "Config error", "es": "Error de configuración", "de": "Konfigurationsfehler",
        "fr": "Erreur de configuration", "it": "Errore configurazione", "pt": "Erro de configuração", "zh": "配置解析错误", "ja": "設定エラー", "uk": "Помилка конфігу"
    },
}


def t(key: str, default: Optional[str] = None) -> str:
    from settings import Settings
    lang = getattr(Settings, "language", "ru")
    if lang not in LANGUAGES:
        lang = "ru"

    entry = TRANSLATIONS.get(key)
    if entry:
        val = entry.get(lang)
        if val:
            return val
        val_ru = entry.get("ru")
        if val_ru:
            return val_ru

    return default if default is not None else key
