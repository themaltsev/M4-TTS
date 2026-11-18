Option Explicit
If WScript.Arguments.Count < 1 Then WScript.Quit 2
Dim shell, executable
Set shell = CreateObject("WScript.Shell")
executable = WScript.Arguments(0)
shell.Run Chr(34) & executable & Chr(34) & " tray", 0, False
