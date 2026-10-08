(function () {
    $.global.METEO_TEMPERATURE_UPDATED = false;
    $.global.METEO_TEMPERATURE_UPDATE_ERROR = null;

    var rootPath = "C:/Users/Aruba IA/Documents/APPS/Meteo";
    var requestPath = rootPath + "/temperature_template/project/update_request.json";

    function readJson(path) {
        var file = new File(path);
        if (!file.exists) throw new Error("No existe: " + path);
        file.encoding = "UTF-8";
        file.open("r");
        var value = eval("(" + file.read() + ")");
        file.close();
        return value;
    }

    function writeLog(path, message) {
        var file = new File(path);
        file.encoding = "UTF-8";
        file.open("w");
        file.write(message);
        file.close();
    }

    function findFootage(name) {
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof FootageItem && item.name === name) return item;
        }
        throw new Error("No se encuentra el metraje: " + name);
    }

    try {
        if (!app.project || app.project.numItems === 0 || !app.project.file) {
            throw new Error("Abre primero un proyecto de la plantilla de temperaturas.");
        }
        var request = readJson(requestPath);
        if (!request.date || !request.texture_path) {
            throw new Error("update_request.json no contiene date y texture_path");
        }
        var source = new File(request.texture_path);
        if (!source.exists) {
            throw new Error("No existe la textura diaria: " + request.texture_path);
        }

        app.beginUndoGroup("Actualizar temperatura diaria");
        findFootage("TEMPERATURA_DIARIA_REEMPLAZAR").replace(source);
        app.project.save(app.project.file);
        app.endUndoGroup();

        var logPath = rootPath + "/temperature_template/validation/phase6_after_effects_update_" +
            request.date + ".log";
        writeLog(
            logPath,
            "OK\n" +
            "Fecha: " + request.date + "\n" +
            "Proyecto: " + app.project.file.fsName + "\n" +
            "Textura: " + source.fsName + "\n"
        );
        $.global.METEO_TEMPERATURE_UPDATED = true;
        if (!$.global.METEO_TEMPLATE_SUPPRESS_ALERTS) {
            alert("Temperatura actualizada con la fecha " + request.date + ".");
        }
    } catch (error) {
        try { app.endUndoGroup(); } catch (ignoreUndo) {}
        $.global.METEO_TEMPERATURE_UPDATE_ERROR = error.toString();
        if (!$.global.METEO_TEMPLATE_SUPPRESS_ALERTS) {
            alert("No se pudo actualizar la temperatura:\n" + error.toString());
        }
    }
}());
