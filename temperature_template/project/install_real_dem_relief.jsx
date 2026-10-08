(function () {
    $.global.METEO_RELIEF_INSTALLED = false;
    $.global.METEO_RELIEF_ERROR = null;

    var rootPath = "C:/Users/Aruba IA/Documents/APPS/Meteo";
    var projectPath = rootPath + "/temperature_template/project/Mapa_Temperaturas_Semiautomatico.aep";
    var reliefPath = rootPath + "/temperature_template/assets/static/relieve_dem.png";
    var logPath = rootPath + "/temperature_template/validation/phase5_after_effects.log";
    var workingProject = null;

    function writeLog(message) {
        var file = new File(logPath);
        file.encoding = "UTF-8";
        file.open("w");
        file.write(message);
        file.close();
    }

    function findItem(name, kind) {
        for (var i = 1; i <= workingProject.numItems; i++) {
            var item = workingProject.item(i);
            if (item.name !== name) continue;
            if (!kind) return item;
            if (kind === "comp" && item instanceof CompItem) return item;
            if (kind === "folder" && item instanceof FolderItem) return item;
            if (kind === "footage" && item instanceof FootageItem) return item;
        }
        return null;
    }

    try {
        var projectFile = new File(projectPath);
        var reliefFile = new File(reliefPath);
        if (!projectFile.exists) throw new Error("No existe el proyecto: " + projectPath);
        if (!reliefFile.exists) throw new Error("No existe el relieve: " + reliefPath);

        workingProject = app.project;
        if (!workingProject || !workingProject.file || workingProject.file.fsName !== projectFile.fsName) {
            workingProject = app.open(projectFile);
        }
        app.beginUndoGroup("Instalar relieve DEM real");

        var comp = findItem("TEMP_MAPA_MASTER");
        if (!comp) {
            var itemNames = [];
            for (var debugIndex = 1; debugIndex <= workingProject.numItems; debugIndex++) {
                itemNames.push(workingProject.item(debugIndex).name);
            }
            throw new Error(
                "No se encuentra TEMP_MAPA_MASTER. Archivo=" +
                (workingProject.file ? workingProject.file.fsName : "sin archivo") +
                "; elementos=" + workingProject.numItems +
                "; nombres=" + itemNames.join(" | ")
            );
        }
        var reliefLayer = comp.layer("03_RELIEVE_PENDIENTE_DEM");
        if (!reliefLayer) throw new Error("No se encuentra la capa de relieve");

        var staticFolder = findItem("01_ESTATICOS");
        var footage = findItem("RELIEVE_DEM_REAL");
        if (footage) {
            footage.replace(reliefFile);
        } else {
            footage = workingProject.importFile(new ImportOptions(reliefFile));
            footage.name = "RELIEVE_DEM_REAL";
            if (staticFolder) footage.parentFolder = staticFolder;
        }

        reliefLayer.replaceSource(footage, false);
        reliefLayer.name = "03_RELIEVE_DEM_REAL";
        reliefLayer.enabled = true;
        reliefLayer.blendingMode = BlendingMode.SOFT_LIGHT;
        reliefLayer.property("ADBE Transform Group").property("ADBE Opacity").expression =
            "thisComp.layer(\"00_CONTROLES_PLANTILLA\").effect(\"Intensidad relieve\")(1)";
        reliefLayer.comment =
            "Sombreado ETOPO 2022. Luz suave; intensidad controlada por 00_CONTROLES_PLANTILLA.";

        var controller = comp.layer("00_CONTROLES_PLANTILLA");
        var effect = controller.effect("Intensidad relieve");
        if (effect) effect.property(1).setValue(50);

        workingProject.save(projectFile);
        app.endUndoGroup();
        $.global.METEO_RELIEF_INSTALLED = true;
        writeLog(
            "OK\n" +
            "Proyecto: " + projectPath + "\n" +
            "Relieve: " + reliefPath + "\n" +
            "Capa: 03_RELIEVE_DEM_REAL\n" +
            "Fusion: SOFT_LIGHT\n" +
            "Intensidad: 50\n"
        );
        if (!$.global.METEO_TEMPLATE_SUPPRESS_ALERTS) {
            alert("Relieve DEM instalado correctamente.");
        }
    } catch (error) {
        try { app.endUndoGroup(); } catch (ignoreUndo) {}
        $.global.METEO_RELIEF_ERROR = error.toString();
        writeLog("ERROR\n" + error.toString() + "\n");
        if (!$.global.METEO_TEMPLATE_SUPPRESS_ALERTS) {
            alert("No se pudo instalar el relieve:\n" + error.toString());
        }
    }
}());
