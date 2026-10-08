(function () {
    var rootPath = "C:/Users/Aruba IA/Documents/APPS/Meteo";
    var projectFile = new File(rootPath + "/METEO FINAL.aep");
    var applyScript = new File(rootPath + "/tools/apply_daily_data.jsx");

    function sameFile(left, right) {
        return left && right && left.absoluteURI === right.absoluteURI;
    }

    try {
        if (!projectFile.exists) {
            throw new Error("No existe el proyecto: " + projectFile.fsName);
        }
        if (!applyScript.exists) {
            throw new Error("No existe el script diario: " + applyScript.fsName);
        }

        var currentProject = app.project;
        var targetIsOpen = currentProject && sameFile(currentProject.file, projectFile);
        var emptyUntitledProject = currentProject && !currentProject.file && currentProject.numItems === 0;

        if (!targetIsOpen) {
            if (currentProject && !emptyUntitledProject) {
                throw new Error(
                    "After Effects ya tiene abierto otro proyecto. Guardalo o cierralo y vuelve a ejecutar la automatizacion."
                );
            }
            app.open(projectFile);
        }

        $.evalFile(applyScript);
        if (!$.global.METEO_APPLY_SUCCEEDED) {
            throw new Error($.global.METEO_LAST_ERROR || "El script diario no confirmo su ejecucion.");
        }
    } catch (error) {
        alert("No se pudo completar la automatizacion diaria:\n" + error.toString());
    }
}());
