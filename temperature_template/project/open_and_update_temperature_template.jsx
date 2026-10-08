(function () {
    var rootPath = "C:/Users/Aruba IA/Documents/APPS/Meteo";
    var requestFile = new File(
        rootPath + "/temperature_template/project/update_request.json"
    );
    var updateScript = new File(
        rootPath + "/temperature_template/project/update_temperature_daily.jsx"
    );

    function readJson(file) {
        file.encoding = "UTF-8";
        file.open("r");
        var value = eval("(" + file.read() + ")");
        file.close();
        return value;
    }

    function sameFile(left, right) {
        return left && right && left.absoluteURI === right.absoluteURI;
    }

    try {
        if (!requestFile.exists) throw new Error("No existe update_request.json");
        if (!updateScript.exists) throw new Error("No existe update_temperature_daily.jsx");
        var request = readJson(requestFile);
        var projectFile = new File(request.project_path);
        if (!projectFile.exists) throw new Error("No existe el proyecto: " + request.project_path);

        var currentProject = app.project;
        var targetIsOpen = currentProject && sameFile(currentProject.file, projectFile);
        var emptyUntitledProject = currentProject && !currentProject.file && currentProject.numItems === 0;
        if (!targetIsOpen) {
            if (currentProject && !emptyUntitledProject) {
                throw new Error(
                    "After Effects ya tiene abierto otro proyecto. Guardalo o cierralo antes de actualizar."
                );
            }
            app.open(projectFile);
        }

        $.global.METEO_TEMPLATE_SUPPRESS_ALERTS = true;
        $.evalFile(updateScript);
        if (!$.global.METEO_TEMPERATURE_UPDATED) {
            throw new Error(
                $.global.METEO_TEMPERATURE_UPDATE_ERROR ||
                "El actualizador no confirmo el reemplazo."
            );
        }
    } catch (error) {
        alert("No se pudo actualizar la plantilla termica:\n" + error.toString());
    }
}());
