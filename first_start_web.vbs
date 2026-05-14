Option Explicit

Dim shell, fso, projectRoot, startScript, rc, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)
startScript = fso.BuildPath(projectRoot, "start_web_app.vbs")

If Not fso.FileExists(startScript) Then
    MsgBox "Not found: " & startScript, vbCritical, "Fire Data"
    WScript.Quit 1
End If

cmd = "cscript //nologo """ & startScript & """"
rc = shell.Run(cmd, 0, True)
If rc = 0 Then
    MsgBox "First start completed successfully.", vbInformation, "Fire Data"
Else
    MsgBox "First start failed. Code: " & CStr(rc), vbCritical, "Fire Data"
End If
WScript.Quit rc
