(function () {
    var output = new File(
        "C:/Users/Aruba IA/Documents/APPS/Meteo/temperature_template/validation/after_effects_smoke_test.log"
    );
    output.encoding = "UTF-8";
    output.open("w");
    output.write("OK\nAfter Effects ExtendScript operativo\n");
    output.close();
    app.quit();
}());
