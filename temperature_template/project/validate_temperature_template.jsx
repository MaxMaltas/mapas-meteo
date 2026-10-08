(function () {
    var projectPath =
        "C:/Users/Aruba IA/Documents/APPS/Meteo/temperature_template/project/Mapa_Temperaturas_Semiautomatico.aep";
    var reportPath =
        "C:/Users/Aruba IA/Documents/APPS/Meteo/temperature_template/validation/phase4_project_validation.txt";
    var lines = [];

    function line(value) {
        lines.push(String(value));
    }

    function writeReport() {
        var report = new File(reportPath);
        report.encoding = "UTF-8";
        report.open("w");
        report.write(lines.join("\n") + "\n");
        report.close();
    }

    try {
        var projectFile = new File(projectPath);
        if (!projectFile.exists) throw new Error("No existe el proyecto");
        app.open(projectFile);
        var master = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === "TEMP_MAPA_MASTER") {
                master = item;
                break;
            }
        }
        if (!master) throw new Error("No existe TEMP_MAPA_MASTER");

        line("STATUS=OK");
        line("PROJECT=" + projectPath);
        line("BITS_PER_CHANNEL=" + app.project.bitsPerChannel);
        line("COMP=" + master.name);
        line("SIZE=" + master.width + "x" + master.height);
        line("FPS=" + master.frameRate);
        line("DURATION=" + master.duration);
        line("LAYERS=" + master.numLayers);
        for (var layerIndex = 1; layerIndex <= master.numLayers; layerIndex++) {
            var layer = master.layer(layerIndex);
            var sourceName = layer.source ? layer.source.name : "SIN_METRAJE";
            line(
                "LAYER_" + layerIndex + "=" + layer.name +
                "|enabled=" + layer.enabled +
                "|locked=" + layer.locked +
                "|source=" + sourceName
            );
        }
        writeReport();
        app.quit();
    } catch (error) {
        line("STATUS=ERROR");
        line("ERROR=" + error.toString());
        writeReport();
        app.quit();
    }
}());
