using System;
using System.Data;
using System.Globalization;
using System.Text;
using BinaryAssetBuilder.Core.SageXml;

namespace BinaryAssetBuilder.Core
{
    // Native, cross-platform replacement for the Framework-only BinaryAssetBuilder.ExpressionEval.dll.
    // SAGE attribute/value expressions begin with '=' and may reference #define names as $NAME (or
    // $(NAME)) plus arithmetic, e.g. "=$SOME_DEFINE * 2 + 5". Defines are substituted with their
    // values and the arithmetic is computed. Non-expression values pass through unchanged.
    public class ExpressionEvaluator : IExpressionEvaluator
    {
        private readonly AssetDeclarationDocument _document;

        public ExpressionEvaluator(AssetDeclarationDocument document)
        {
            _document = document;
        }

        public void EvaluateDefinition(Definition definition)
        {
            definition.EvaluatedValue = Evaluate(definition.OriginalValue);
        }

        public string Evaluate(string expression)
        {
            if (string.IsNullOrEmpty(expression) || expression[0] != '=')
            {
                return expression;
            }
            string body = expression.Substring(1);
            string substituted = SubstituteDefines(body);
            try
            {
                object result = new DataTable().Compute(substituted, null);
                return Convert.ToString(result, CultureInfo.InvariantCulture);
            }
            catch
            {
                // not arithmetic (e.g. a string/enum define) — return the substituted text
                return substituted.Trim();
            }
        }

        private string SubstituteDefines(string expr)
        {
            StringBuilder sb = new StringBuilder();
            int i = 0;
            while (i < expr.Length)
            {
                char c = expr[i];
                if (c == '$')
                {
                    i++;
                    bool paren = i < expr.Length && expr[i] == '(';
                    if (paren) { i++; }
                    int start = i;
                    while (i < expr.Length && (char.IsLetterOrDigit(expr[i]) || expr[i] == '_')) { i++; }
                    string name = expr.Substring(start, i - start);
                    if (paren && i < expr.Length && expr[i] == ')') { i++; }
                    if (_document.AllDefines.TryGetValue(name, out Definition def) && def.EvaluatedValue is not null)
                    {
                        sb.Append(def.EvaluatedValue);
                    }
                    else
                    {
                        sb.Append(name);
                    }
                }
                else
                {
                    sb.Append(c);
                    i++;
                }
            }
            return sb.ToString();
        }
    }
}
