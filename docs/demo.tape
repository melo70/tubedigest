# File: docs/demo.tape
# Genera la GIF di anteprima animata per il README di GitHub
# Esegui dal terminale con: vhs docs/demo.tape

Output assets/demo.gif

Set FontSize 14
Set Width 1080
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

# 2. Scheda tecnica e ispezione dettagliata del singolo video (layout a tabella a 2 colonne)
Type "clear"
Enter
Sleep 300ms
Type "./tubedigest --video-details sEpUqv_5bGY"
Sleep 500ms
Enter
Sleep 4s

# 3. Gran finale: Lettura del riassunto AI con pager 'less' (mostra l'header e la panoramica intatti)
Type "clear"
Enter
Sleep 300ms
Type "CLICOLOR_FORCE=1 ./tubedigest --show-summary sEpUqv_5bGY | less -R"
Sleep 500ms
Enter
Sleep 5s
Type "q"
Sleep 1.5s
