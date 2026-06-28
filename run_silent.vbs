Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)

If Not fso.FileExists(appDir & "\venv\Scripts\activate.bat") Then
    MsgBox "venv не найден." & vbCrLf & vbCrLf & "Выполните setup.cmd", vbCritical, "Clerkonator"
    WScript.Quit 1
End If

cmd = "cmd /c ""cd /d """ & appDir & """ && call scripts\_stt_venv.cmd && pythonw main.py"""
shell.Run cmd, 0, False
