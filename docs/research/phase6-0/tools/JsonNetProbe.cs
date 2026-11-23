// Ensayo local independiente: no abre conexiones ni imprime el guardado.
using System;
using System.IO;
using System.Text;
using Newtonsoft.Json;

public sealed class BlobPayload
{
    [JsonProperty("data", Required = Required.Default, NullValueHandling = NullValueHandling.Ignore)]
    public string Data { get; set; }
}

public static class JsonNetProbe
{
    public static void Main(string[] args)
    {
        if (args.Length != 2) throw new ArgumentException("Entrada privada y salida privada requeridas");
        var aggregate = File.ReadAllText(args[0], new UTF8Encoding(false, true));
        var json = JsonConvert.SerializeObject(new BlobPayload { Data = aggregate }, new JsonSerializerSettings());
        File.WriteAllText(args[1], json, new UTF8Encoding(false));
        Console.WriteLine("Caracteres del sobre: " + json.Length);
    }
}
