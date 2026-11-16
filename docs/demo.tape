# File: docs/demo.tape
# Genera la GIF di anteprima animata per il README di GitHub
# Esegui dal terminale con: vhs docs/demo.tape

Output assets/demo.gif

Set FontSize 14
Set Width 1280
Set Height 720
Set Padding 20
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set TypingSpeed 50ms

# 1. Panoramica dei canali YouTube monitorati (ASCII Gradient Banner + Canali attivi)
Type "./tubedigest --list-channels"
Sleep 500ms
Enter
Sleep 3.5s

# 2. Esplorazione dell'archivio video elaborati in SQLite
Type "clear"
Enter
Sleep 300ms
Type "./tubedigest --list-videos"
Sleep 500ms
Enter
Sleep 3.5s

# 3. Scheda tecnica e ispezione del singolo video (nuovo layout a tabella verticale)
Type "clear"
Enter
Sleep 300ms
Type "./tubedigest --video-details sEpUqv_5bGY"
Sleep 500ms
Enter
Sleep 4s

# 4. Gran finale: Lettura a terminale del riassunto AI generato da Gemini
Type "clear"
Enter
Sleep 300ms
Type "./tubedigest --show-summary sEpUqv_5bGY"
Sleep 500ms
Enter
Sleep 5.5s
