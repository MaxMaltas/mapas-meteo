(function () {
    var rootPath = "C:/Users/Aruba IA/Documents/APPS/Meteo";
    var projectPath = rootPath + "/METEO FINAL.aep";
    var applyScriptPath = rootPath + "/tools/apply_daily_data.jsx";
    var dataPath = rootPath + "/data/generated/latest/meteo.json";
    var configPath = rootPath + "/config/meteo.json";
    var reportPath = rootPath + "/after_effects_apply_test.txt";

    function readJson(path) {
        var file = new File(path);
        file.encoding = "UTF-8";
        if (!file.open("r")) throw new Error("No se puede abrir: " + path);
        var value = eval("(" + file.read() + ")");
        file.close();
        return value;
    }

    function findComp(name) {
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === name) return item;
        }
        throw new Error("No se encuentra la composición: " + name);
    }

    function textOf(layer) {
        return String(layer.property("ADBE Text Properties").property("ADBE Text Document").value.text);
    }

    function assertEqual(actual, expected, description) {
        if (String(actual) !== String(expected)) {
            throw new Error(description + ": esperado '" + expected + "', obtenido '" + actual + "'");
        }
    }

    var lines = [];
    try {
        app.open(new File(projectPath));
        $.global.METEO_SUPPRESS_ALERTS = true;
        $.evalFile(new File(applyScriptPath));
        if (!$.global.METEO_APPLY_SUCCEEDED) {
            throw new Error($.global.METEO_LAST_ERROR || "El script no confirmó su ejecución");
        }

        var data = readJson(dataPath);
        var config = readJson(configPath);
        var tempComp = findComp(config.after_effects.temperature_comp);
        var previsionComp = findComp(config.after_effects.prevision_comp);
        var doubleComp = findComp(config.after_effects.double_comp);
        var alertsComp = findComp("ALERTAS");
        var temperatureMapComp = findComp("TEMP");
        var generatedPath = rootPath + "/data/generated/" + data.clips.TEMPERATURAS.date;
        var alertsFile = new File(generatedPath + "/alertas_final.png");
        if (alertsFile.exists) {
            assertEqual(
                alertsComp.layer(1).source.name,
                "alertas_final.png",
                "Imagen de ALERTAS"
            );
            assertEqual(alertsComp.layer(1).enabled, true, "Capa de ALERTAS activa");
        } else {
            assertEqual(alertsComp.layer(1).enabled, false, "Capa de ALERTAS inactiva");
        }
        assertEqual(
            temperatureMapComp.layer(2).source.name,
            "temperaturas_final.png",
            "Imagen de TEMP"
        );
        var temperatures = data.clips.TEMPERATURAS.values;
        for (var t = 0; t < temperatures.length; t++) {
            if (temperatures[t].enabled === false) continue;
            assertEqual(
                textOf(tempComp.layer(Number(temperatures[t].ae_layer_index))),
                Math.round(temperatures[t].max_c),
                "Temperatura " + temperatures[t].slot
            );
        }

        var prevision = data.clips.PREVISION.zones;
        for (var p = 0; p < prevision.length; p++) {
            if (prevision[p].enabled === false) continue;
            assertEqual(
                previsionComp.layer(Number(prevision[p].prevision_layer_index)).source.name,
                config.symbol_files[prevision[p].symbol],
                "Previsión " + prevision[p].slot
            );
        }

        assertEqual(
            textOf(doubleComp.layer(Number(config.after_effects.double_day_1_text_layer))),
            data.clips.DOBLE.day_1.weekday,
            "Texto del primer día"
        );
        assertEqual(
            textOf(doubleComp.layer(Number(config.after_effects.double_day_2_text_layer))),
            data.clips.DOBLE.day_2.weekday,
            "Texto del segundo día"
        );

        var day1 = data.clips.DOBLE.day_1.zones;
        var day2 = data.clips.DOBLE.day_2.zones;
        for (var d = 0; d < day1.length; d++) {
            if (day1[d].enabled !== false) {
                assertEqual(
                    doubleComp.layer(Number(day1[d].doble_day_1_layer_index)).source.name,
                    config.symbol_files[day1[d].symbol],
                    "Doble día 1 " + day1[d].slot
                );
            }
            if (day2[d].enabled !== false) {
                assertEqual(
                    doubleComp.layer(Number(day2[d].doble_day_2_layer_index)).source.name,
                    config.symbol_files[day2[d].symbol],
                    "Doble día 2 " + day2[d].slot
                );
            }
        }

        lines.push("OK");
        lines.push("Temperaturas verificadas: " + temperatures.length);
        lines.push("Previsión verificada: " + prevision.length);
        lines.push("Doble día 1 verificado: " + day1.length);
        lines.push("Doble día 2 verificado: " + day2.length);
        lines.push(alertsFile.exists ? "Imágenes de TEMP y ALERTAS verificadas" : "Imagen de TEMP verificada; ALERTAS omitida");
    } catch (error) {
        lines.push("ERROR");
        lines.push(error.toString());
    } finally {
        var report = new File(reportPath);
        report.encoding = "UTF-8";
        report.open("w");
        report.write(lines.join("\n"));
        report.close();
        if (app.project) app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
        app.quit();
    }
}());
