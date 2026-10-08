(function () {
    var projectPath = "C:/Users/Aruba IA/Documents/APPS/Meteo/METEO FINAL.aep";
    var reportPath = "C:/Users/Aruba IA/Documents/APPS/Meteo/after_effects_structure.txt";

    function clean(value) {
        if (value === null || value === undefined) return "";
        return String(value).replace(/\r?\n/g, "\\n").replace(/\t/g, " ");
    }

    function layerKind(layer) {
        if (layer instanceof TextLayer) return "TextLayer";
        if (layer instanceof ShapeLayer) return "ShapeLayer";
        if (layer instanceof CameraLayer) return "CameraLayer";
        if (layer instanceof LightLayer) return "LightLayer";
        if (layer instanceof AVLayer) return "AVLayer";
        return "Layer";
    }

    function formatValue(value) {
        if (value instanceof Array) return value.join(",");
        return String(value);
    }

    function walkProperties(group, prefix, lines) {
        if (!group || !group.numProperties) return;
        for (var p = 1; p <= group.numProperties; p++) {
            var prop = group.property(p);
            if (!prop) continue;
            var path = prefix + "/" + clean(prop.name);
            try {
                if (prop.canSetExpression && prop.expressionEnabled) {
                    lines.push("    EXPRESSION\t" + path + "\t" + clean(prop.expression));
                }
            } catch (ignoreExpression) {}
            try {
                if (prop.numKeys && prop.numKeys > 0) {
                    lines.push("    KEYFRAMES\t" + path + "\t" + prop.numKeys);
                }
            } catch (ignoreKeys) {}
            try {
                if (prop.numProperties && prop.numProperties > 0) {
                    walkProperties(prop, path, lines);
                }
            } catch (ignoreChildren) {}
        }
    }

    try {
        var input = new File(projectPath);
        if (!input.exists) throw new Error("No se encuentra el proyecto: " + projectPath);

        app.open(input);
        var lines = [];
        lines.push("PROJECT\t" + clean(app.project.file ? app.project.file.fsName : ""));
        lines.push("ITEMS\t" + app.project.numItems);

        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem) {
                lines.push("");
                lines.push("COMP\t" + clean(item.name) + "\t" + item.width + "x" + item.height + "\tduration=" + item.duration + "\tfps=" + item.frameRate + "\tlayers=" + item.numLayers);
                for (var l = 1; l <= item.numLayers; l++) {
                    var layer = item.layer(l);
                    var sourceName = "";
                    try { sourceName = layer.source ? layer.source.name : ""; } catch (ignoreSource) {}
                    var parentName = "";
                    try { parentName = layer.parent ? layer.parent.name : ""; } catch (ignoreParent) {}
                    lines.push("  LAYER\t" + l + "\t" + layerKind(layer) + "\t" + clean(layer.name) + "\tsource=" + clean(sourceName) + "\tin=" + layer.inPoint + "\tout=" + layer.outPoint + "\tstart=" + layer.startTime + "\t3d=" + layer.threeDLayer + "\tenabled=" + layer.enabled + "\tparent=" + clean(parentName));
                    try {
                        var transform = layer.property("ADBE Transform Group");
                        lines.push("    TRANSFORM\tposition=" + formatValue(transform.property("ADBE Position").value) + "\tscale=" + formatValue(transform.property("ADBE Scale").value) + "\trotation=" + formatValue(transform.property("ADBE Rotate Z").value));
                    } catch (ignoreTransform) {}

                    if (layer instanceof TextLayer) {
                        try {
                            var textDocument = layer.property("ADBE Text Properties").property("ADBE Text Document").value;
                            lines.push("    TEXT\t" + clean(textDocument.text) + "\tfont=" + clean(textDocument.font) + "\tsize=" + textDocument.fontSize);
                        } catch (ignoreText) {}
                    }

                    try {
                        var effects = layer.property("ADBE Effect Parade");
                        for (var e = 1; effects && e <= effects.numProperties; e++) {
                            var effect = effects.property(e);
                            lines.push("    EFFECT\t" + clean(effect.name) + "\tmatch=" + clean(effect.matchName));
                        }
                    } catch (ignoreEffects) {}

                    try {
                        var masks = layer.property("ADBE Mask Parade");
                        if (masks && masks.numProperties > 0) lines.push("    MASKS\t" + masks.numProperties);
                    } catch (ignoreMasks) {}

                    walkProperties(layer, clean(layer.name), lines);
                }
            } else if (item instanceof FootageItem) {
                var fileName = "";
                try { fileName = item.file ? item.file.fsName : ""; } catch (ignoreFile) {}
                lines.push("FOOTAGE\t" + clean(item.name) + "\t" + clean(fileName) + "\t" + item.width + "x" + item.height);
            } else if (item instanceof FolderItem) {
                lines.push("FOLDER\t" + clean(item.name));
            }
        }

        var output = new File(reportPath);
        output.encoding = "UTF-8";
        output.open("w");
        output.write(lines.join("\n"));
        output.close();
        app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
        app.quit();
    } catch (error) {
        var errorFile = new File(reportPath);
        errorFile.encoding = "UTF-8";
        errorFile.open("w");
        errorFile.write("ERROR\t" + clean(error.toString()) + "\nLINE\t" + error.line);
        errorFile.close();
        try { app.quit(); } catch (ignoreQuit) {}
    }
}());
