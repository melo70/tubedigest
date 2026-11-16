# File: docs/demo.tape
Output assets/demo.gif

Set FontSize 14
Set Width 1080
Set Height 720
Set Padding 20
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set TypingSpeed 60ms

# Avvio visualizzazione canali
Type "./tubedigest --list-channels"
Sleep 500ms
Enter
Sleep 3.5s

# Ispezione dettagli video
Type "./tubedigest --video-details sEpUqv_5bGY"
Sleep 500ms
Enter
Sleep 4.5s
