using Relo;
using SageBinaryData;

public static partial class Marshaler
{
    public static unsafe void Marshal(Node node, MultiplayerColor* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        // MetaGameSide is an xs:attribute, stored inline as an AnsiString (e.g. "NOD"/"GDI") immediately after
        // Base — allocated before TooltipName, so marshal it first to match the shipped string-data order.
        Marshal(node.GetAttributeValue(nameof(MultiplayerColor.MetaGameSide), null), &objT->MetaGameSide, state);
        Marshal(node.GetChildNode(nameof(MultiplayerColor.RGBColor), null), &objT->RGBColor, state);
        Marshal(node.GetChildNode(nameof(MultiplayerColor.RGBColorT), null), &objT->RGBColorT, state);
        Marshal(node.GetChildNode(nameof(MultiplayerColor.RGBNightColor), null), &objT->RGBNightColor, state);
        Marshal(node.GetChildNode(nameof(MultiplayerColor.LivingWorldColor), null), &objT->LivingWorldColor, state);
        Marshal(node.GetChildNode(nameof(MultiplayerColor.LivingWorldBannerColor), null), &objT->LivingWorldBannerColor, state);
        Marshal(node.GetChildNode(nameof(MultiplayerColor.TooltipName), null), &objT->TooltipName, state);
        Marshal(node.GetChildNode(nameof(MultiplayerColor.AvailableInMetaGame), null), &objT->AvailableInMetaGame, state);
        Marshal(node, (BaseAssetType*)objT, state);
    }
}