(function () {
    var rootPath = "C:/Users/Aruba IA/Documents/APPS/Meteo";
    var requestFile = new File(
        rootPath + "/temperature_template/project/render_request.json"
    );
    var request = null;

    function readJson(file) {
        file.encoding = "UTF-8";
        file.open("r");
        var value = eval("(" + file.read() + ")");
        file.close();
        return value;
    }

    function writeLog(message) {
        if (!request || !request.log_path) return;
        var file = new File(request.log_path);
        file.encoding = "UTF-8";
        file.open("w");
        file.write(message);
        file.close();
    }

    function findComposition(name) {
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === name) return item;
        }
        return null;
    }

    function chooseImageTemplate(templates) {
        var firstPng = null;
        var firstTiff = null;
        var firstPhotoshop = null;
        for (var i = 0; i < templates.length; i++) {
            var name = templates[i];
            var lower = name.toLowerCase();
            if (lower.indexOf("png") >= 0) {
                if (!firstPng) firstPng = name;
                if (lower.indexOf("alpha") >= 0) return { name: name, extension: ".png" };
            }
            if (lower.indexOf("tiff") >= 0 && !firstTiff) firstTiff = name;
            if (lower.indexOf("photoshop") >= 0 && !firstPhotoshop) firstPhotoshop = name;
        }
        if (firstPng) return { name: firstPng, extension: ".png" };
        if (firstTiff) return { name: firstTiff, extension: ".tif" };
        if (firstPhotoshop) return { name: firstPhotoshop, extension: ".psd" };
        return null;
    }

    try {
        if (!requestFile.exists) throw new Error("No existe render_request.json");
        request = readJson(requestFile);
        var projectFile = new File(request.project_path);
        var outputFile = new File(request.output_path);
        if (!projectFile.exists) throw new Error("No existe el proyecto: " + request.project_path);
        if (!outputFile.parent.exists) outputFile.parent.create();

        app.open(projectFile);
        var comp = findComposition(request.composition || "TEMP_MAPA_MASTER");
        if (!comp) throw new Error("No se encuentra la composicion solicitada");

        for (var index = 1; index <= app.project.renderQueue.numItems; index++) {
            app.project.renderQueue.item(index).render = false;
        }
        var queueItem = app.project.renderQueue.items.add(comp);
        queueItem.timeSpanStart = 0;
        queueItem.timeSpanDuration = 1.0 / comp.frameRate;
        var outputModule = queueItem.outputModule(1);
        var imageTemplate = chooseImageTemplate(outputModule.templates);
        if (!imageTemplate) {
            throw new Error(
                "No existe una plantilla de imagen fija. Disponibles: " +
                outputModule.templates.join(" | ")
            );
        }
        outputModule.applyTemplate(imageTemplate.name);
        outputFile = new File(
            outputFile.parent.fsName + "/" + request.output_prefix + "_[#####]" +
            imageTemplate.extension
        );
        outputModule.file = outputFile;
        app.project.renderQueue.render();

        var candidates = outputFile.parent.getFiles(function (entry) {
            return entry instanceof File &&
                entry.name.toLowerCase().indexOf(request.output_prefix.toLowerCase()) === 0 &&
                /\.(png|tif|tiff|psd)$/i.test(entry.name);
        });
        if (!candidates.length) throw new Error("After Effects no genero ningun PNG");
        candidates.sort(function (left, right) {
            return right.modified.getTime() - left.modified.getTime();
        });
        writeLog(
            "OK\n" +
            "Fecha: " + request.date + "\n" +
            "Proyecto: " + projectFile.fsName + "\n" +
            "Composicion: " + comp.name + "\n" +
            "Plantilla: " + imageTemplate.name + "\n" +
            "Render: " + candidates[0].fsName + "\n"
        );
        try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch (ignoreClose) {}
    } catch (error) {
        writeLog("ERROR\n" + error.toString() + "\n");
        try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch (ignoreCloseError) {}
    }
}());
