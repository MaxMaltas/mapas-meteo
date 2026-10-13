(function () {
    $.global.METEO_APPLY_SUCCEEDED = false;
    $.global.METEO_LAST_ERROR = null;
    var rootPath = "C:/Users/Aruba IA/Documents/APPS/Meteo";
    var jsonPath = rootPath + "/data/generated/latest/meteo.json";
    var configPath = rootPath + "/config/meteo.json";

    function readJson(path) {
        var file = new File(path);
        if (!file.exists) throw new Error("No existe: " + path);
        file.encoding = "UTF-8";
        file.open("r");
        // ExtendScript en algunas versiones de After Effects no incluye JSON.parse.
        // Los dos archivos se generan localmente dentro de este proyecto.
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

    function findFootage(name) {
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof FootageItem && item.name === name) return item;
        }
        var sourceFile = new File(rootPath + "/(Material de archivo)/SIMBOLOS/" + name);
        if (!sourceFile.exists) throw new Error("No se encuentra el metraje: " + name);
        return app.project.importFile(new ImportOptions(sourceFile));
    }

    function importGeneratedImage(path) {
        var sourceFile = new File(path);
        if (!sourceFile.exists) throw new Error("No se encuentra la imagen generada: " + path);

        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (
                item instanceof FootageItem &&
                item.file &&
                item.file.absoluteURI === sourceFile.absoluteURI
            ) {
                item.replace(sourceFile);
                return item;
            }
        }

        return app.project.importFile(new ImportOptions(sourceFile));
    }

    function replaceGeneratedImage(compName, layerIndex, path) {
        var comp = findComp(compName);
        var layer = comp.layer(Number(layerIndex));
        if (!layer || typeof layer.replaceSource !== "function") {
            throw new Error(
                "La capa " + layerIndex + " de " + compName + " no admite imágenes."
            );
        }
        layer.replaceSource(importGeneratedImage(path), false);
    }

    function hasActiveAlerts(alerts) {
        if (!alerts) return false;
        var collections = [alerts.provinces, alerts.zones];
        for (var c = 0; c < collections.length; c++) {
            var entries = collections[c];
            if (!entries) continue;
            for (var i = 0; i < entries.length; i++) {
                var entry = entries[i];
                if (entry.level && String(entry.level).toLowerCase() !== "green") {
                    return true;
                }
                if (entry.alerts && entry.alerts.length > 0) return true;
            }
        }
        return false;
    }

    function applyAlertsImage(path, alerts) {
        var comp = findComp("ALERTAS");
        var layer = comp.layer(1);
        var sourceFile = new File(path);

        if (!sourceFile.exists) {
            if (hasActiveAlerts(alerts)) {
                throw new Error("Hay alertas activas pero no se encuentra la imagen generada: " + path);
            }
            // Evita que quede visible el mapa de alertas de una ejecución anterior.
            layer.enabled = false;
            return;
        }

        replaceGeneratedImage("ALERTAS", 1, path);
        layer.enabled = true;
    }

    function setText(layer, value) {
        var property = layer.property("ADBE Text Properties").property("ADBE Text Document");
        var document = property.value;
        document.text = String(value);
        property.setValue(document);
    }

    function replaceSymbol(comp, layerIndex, symbol, symbolFiles) {
        if (!layerIndex || !symbol) return;
        var sourceName = symbolFiles[symbol];
        if (!sourceName) throw new Error("Símbolo no configurado: " + symbol);
        comp.layer(Number(layerIndex)).replaceSource(findFootage(sourceName), false);
    }

    try {
        if (!app.project || app.project.numItems === 0) {
            throw new Error("Abre primero el proyecto de meteorología.");
        }
        var data = readJson(jsonPath);
        var config = readJson(configPath);
        app.beginUndoGroup("Aplicar datos AEMET");

        if (!data.clips || !data.clips.TEMPERATURAS || !data.clips.TEMPERATURAS.date) {
            throw new Error("El JSON diario no contiene la fecha del mapa de temperaturas.");
        }
        var generatedPath = rootPath + "/data/generated/" + data.clips.TEMPERATURAS.date;
        applyAlertsImage(generatedPath + "/alertas_final.png", data.alerts);
        replaceGeneratedImage("TEMP", 2, generatedPath + "/temperaturas_final.png");

        var tempComp = findComp(config.after_effects.temperature_comp);
        var temperatureValues = data.clips.TEMPERATURAS.values;
        for (var t = 0; t < temperatureValues.length; t++) {
            var temperature = temperatureValues[t];
            var tempLayer = tempComp.layer(Number(temperature.ae_layer_index));
            tempLayer.enabled = temperature.enabled !== false;
            if (temperature.enabled === false) continue;
            if (temperature.max_c !== null && temperature.max_c !== undefined) {
                setText(tempLayer, Math.round(temperature.max_c));
            }
        }

        var previsionComp = findComp(config.after_effects.prevision_comp);
        var previsionZones = data.clips.PREVISION.zones;
        for (var p = 0; p < previsionZones.length; p++) {
            previsionComp.layer(Number(previsionZones[p].prevision_layer_index)).enabled = previsionZones[p].enabled !== false;
            if (previsionZones[p].enabled === false) continue;
            replaceSymbol(
                previsionComp,
                previsionZones[p].prevision_layer_index,
                previsionZones[p].symbol,
                config.symbol_files
            );
        }

        var doubleComp = findComp(config.after_effects.double_comp);
        setText(doubleComp.layer(Number(config.after_effects.double_day_1_text_layer)), data.clips.DOBLE.day_1.weekday);
        setText(doubleComp.layer(Number(config.after_effects.double_day_2_text_layer)), data.clips.DOBLE.day_2.weekday);
        var day1Zones = data.clips.DOBLE.day_1.zones;
        var day2Zones = data.clips.DOBLE.day_2.zones;
        for (var d = 0; d < day1Zones.length; d++) {
            doubleComp.layer(Number(day1Zones[d].doble_day_1_layer_index)).enabled = day1Zones[d].enabled !== false;
            doubleComp.layer(Number(day2Zones[d].doble_day_2_layer_index)).enabled = day2Zones[d].enabled !== false;
            if (day1Zones[d].enabled !== false) {
                replaceSymbol(doubleComp, day1Zones[d].doble_day_1_layer_index, day1Zones[d].symbol, config.symbol_files);
            }
            if (day2Zones[d].enabled !== false) {
                replaceSymbol(doubleComp, day2Zones[d].doble_day_2_layer_index, day2Zones[d].symbol, config.symbol_files);
            }
        }

        app.endUndoGroup();
        $.global.METEO_APPLY_SUCCEEDED = true;
        if (!$.global.METEO_SUPPRESS_ALERTS) {
            alert("Datos AEMET aplicados. Revisa las composiciones antes de exportar.");
        }
    } catch (error) {
        try { app.endUndoGroup(); } catch (ignoreUndo) {}
        $.global.METEO_LAST_ERROR = error.toString();
        if (!$.global.METEO_SUPPRESS_ALERTS) {
            alert("No se pudieron aplicar los datos:\n" + error.toString());
        }
    }
}());
