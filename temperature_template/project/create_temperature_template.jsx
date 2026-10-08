(function () {
    $.global.METEO_TEMPLATE_CREATED = false;
    $.global.METEO_TEMPLATE_ERROR = null;

    var rootPath = "C:/Users/Aruba IA/Documents/APPS/Meteo";
    var templatePath = rootPath + "/temperature_template";
    var staticPath = templatePath + "/assets/vector_master";
    var reliefPath = templatePath + "/assets/static/relieve_dem.png";
    var dailyPath = templatePath + "/assets/daily/2026-10-06";
    var outputPath = templatePath + "/project/Mapa_Temperaturas_Semiautomatico.aep";
    var logPath = templatePath + "/validation/phase4_after_effects.log";

    function writeLog(message) {
        var file = new File(logPath);
        file.encoding = "UTF-8";
        file.open("w");
        file.write(message);
        file.close();
    }

    function requireFile(path) {
        var file = new File(path);
        if (!file.exists) throw new Error("No existe el recurso: " + path);
        return file;
    }

    function importPng(path, name, parentFolder) {
        var options = new ImportOptions(requireFile(path));
        var footage = app.project.importFile(options);
        footage.name = name;
        footage.parentFolder = parentFolder;
        return footage;
    }

    function fitLayer(layer, width, height) {
        layer.property("ADBE Transform Group").property("ADBE Position")
            .setValue([width / 2, height / 2]);
        layer.property("ADBE Transform Group").property("ADBE Scale")
            .setValue([100, 100]);
    }

    function addLayer(comp, footage, name, label, locked) {
        var layer = comp.layers.add(footage);
        layer.name = name;
        layer.label = label;
        layer.locked = locked;
        fitLayer(layer, comp.width, comp.height);
        return layer;
    }

    try {
        if (!app.project) app.newProject();
        if (app.project.numItems !== 0) {
            throw new Error(
                "El proyecto abierto no esta vacio. Cierra el proyecto actual y vuelve a ejecutar este script."
            );
        }

        app.beginUndoGroup("Crear plantilla de temperaturas");
        app.project.bitsPerChannel = 16;

        var assetsFolder = app.project.items.addFolder("01_ASSETS");
        var staticFolder = app.project.items.addFolder("01_ESTATICOS");
        staticFolder.parentFolder = assetsFolder;
        var dailyFolder = app.project.items.addFolder("02_DIARIOS_REEMPLAZABLES");
        dailyFolder.parentFolder = assetsFolder;
        var compsFolder = app.project.items.addFolder("02_COMPOSICIONES");

        var land = importPng(staticPath + "/tierra.png", "TIERRA_BASE", staticFolder);
        var provinces = importPng(staticPath + "/provincias.png", "LIMITES_PROVINCIAS", staticFolder);
        var communities = importPng(staticPath + "/comunidades.png", "LIMITES_COMUNIDADES", staticFolder);
        var relief = importPng(reliefPath, "RELIEVE_DEM_REAL", staticFolder);
        var temperature = importPng(
            dailyPath + "/temperatura_rellenada.png",
            "TEMPERATURA_DIARIA_REEMPLAZAR",
            dailyFolder
        );

        var comp = app.project.items.addComp(
            "TEMP_MAPA_MASTER",
            1920,
            1080,
            1,
            10,
            25
        );
        comp.parentFolder = compsFolder;
        comp.bgColor = [0.886, 0.937, 0.973];

        var background = comp.layers.addSolid(
            [0.886, 0.937, 0.973],
            "00_FONDO_GUIA",
            1920,
            1080,
            1,
            10
        );
        background.label = 8;
        background.locked = true;

        var landLayer = addLayer(comp, land, "01_TIERRA_BASE", 2, true);
        landLayer.enabled = true;

        var temperatureLayer = addLayer(
            comp,
            temperature,
            "02_TEMPERATURA_DIARIA",
            10,
            false
        );
        temperatureLayer.comment =
            "Capa diaria. Sustituir el metraje mediante update_temperature_daily.jsx.";

        var reliefLayer = addLayer(
            comp,
            relief,
            "03_RELIEVE_DEM_REAL",
            9,
            false
        );
        reliefLayer.enabled = true;
        reliefLayer.blendingMode = BlendingMode.SOFT_LIGHT;
        reliefLayer.property("ADBE Transform Group").property("ADBE Opacity").expression =
            "thisComp.layer(\"00_CONTROLES_PLANTILLA\").effect(\"Intensidad relieve\")(1)";
        reliefLayer.comment =
            "Sombreado ETOPO 2022. Luz suave; intensidad controlada por 00_CONTROLES_PLANTILLA.";

        var provinceLayer = addLayer(
            comp,
            provinces,
            "04_LIMITES_PROVINCIAS",
            13,
            true
        );
        provinceLayer.enabled = true;

        var communityLayer = addLayer(
            comp,
            communities,
            "05_LIMITES_COMUNIDADES_COSTA",
            1,
            true
        );
        communityLayer.enabled = true;

        var controller = comp.layers.addNull(10);
        controller.name = "00_CONTROLES_PLANTILLA";
        controller.label = 14;
        controller.moveToBeginning();
        controller.comment =
            "Controles generales de la plantilla termica.";
        var slider = controller.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
        slider.name = "Intensidad relieve";
        slider.property("ADBE Slider Control-0001").setValue(50);

        var marker = new MarkerValue(
            "PLANTILLA TERMICA | Temperatura reemplazable | Relieve DEM real"
        );
        comp.markerProperty.setValueAtTime(0, marker);
        comp.openInViewer();

        var outputFile = new File(outputPath);
        app.project.save(outputFile);
        app.endUndoGroup();

        $.global.METEO_TEMPLATE_CREATED = true;
        writeLog(
            "OK\nProyecto: " + outputPath + "\n" +
            "Composicion: TEMP_MAPA_MASTER\n" +
            "Capas: 7\n"
        );
        if (!$.global.METEO_TEMPLATE_SUPPRESS_ALERTS) {
            alert(
                "Plantilla creada correctamente.\n\n" +
                "Proyecto: " + outputPath + "\n" +
                "Composicion: TEMP_MAPA_MASTER"
            );
        }
    } catch (error) {
        try { app.endUndoGroup(); } catch (ignoreUndo) {}
        $.global.METEO_TEMPLATE_ERROR = error.toString();
        writeLog("ERROR\n" + error.toString() + "\n");
        if (!$.global.METEO_TEMPLATE_SUPPRESS_ALERTS) {
            alert("No se pudo crear la plantilla:\n" + error.toString());
        }
    }
}());
