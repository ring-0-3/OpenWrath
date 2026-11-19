using System.Reflection;
using BinaryAssetBuilder.Core.Diagnostics;
using BinaryAssetBuilder.Core.SageXml;

namespace BinaryAssetBuilder.Core
{
    public class ExpressionEvaluatorWrapper
    {
        private static readonly Tracer _tracer = Tracer.GetTracer(nameof(ExpressionEvaluatorWrapper), "Provides expression evaluation functionality");
        private static Assembly _library;

        public static void LoadAssembly()
        {
            try
            {
                _library = Assembly.Load("BinaryAssetBuilder.ExpressionEval");
                _library.GetType("BinaryAssetBuilder.ExpressionEval.ExpressionEvaluator");
            }
            catch
            {
                _library = null;
                _tracer.TraceError("Could not load ExpressionEvaluator from BinaryAssetBuilder.ExpressionEval.dll. Expressions are disabled.");
            }
        }

        public static IExpressionEvaluator GetEvaluator(AssetDeclarationDocument document)
        {
            // Use the native cross-platform evaluator (the Framework ExpressionEval.dll won't load on .NET/Linux).
            return new ExpressionEvaluator(document);
        }
    }
}
