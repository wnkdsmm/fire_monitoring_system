Option Explicit

Dim shell, fso, projectRoot, startScript, rc, cmd, silentSuccess
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
silentSuccess = (LCase(Trim(GetArg(0))) = "--silent-success")

projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)
startScript = fso.BuildPath(projectRoot, "start_web_app.vbs")

If Not fso.FileExists(startScript) Then
    Notify "Not found: " & startScript, vbCritical, "Fire Data"
    WScript.Quit 1
End If

cmd = "cscript //nologo """ & startScript & """ --lite"
If silentSuccess Then
    cmd = cmd & " --silent-success"
End If
rc = shell.Run(cmd, 0, True)
If rc = 0 Then
    If Not silentSuccess Then
        Notify "Start completed successfully.", vbInformation, "Fire Data"
    End If
Else
    Notify "Start failed. Code: " & CStr(rc), vbCritical, "Fire Data"
End If
WScript.Quit rc

Function GetArg(index)
    If WScript.Arguments.Count > index Then
        GetArg = WScript.Arguments(index)
    Else
        GetArg = ""
    End If
End Function

Sub Notify(text, flags, title)
    CreateObject("WScript.Shell").Popup text, 5, title, flags
End Sub
