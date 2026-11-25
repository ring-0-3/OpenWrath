using Relo;
using SageBinaryData;

public static partial class Marshaler
{
    public static unsafe void Marshal(Node node, BaseRenderAssetType* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node, (BaseAssetType*)objT, state);
    }

    public static unsafe void Marshal(Node node, Vector2* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(Vector2.X), null), &objT->X, state);
        Marshal(node.GetAttributeValue(nameof(Vector2.Y), null), &objT->Y, state);
    }

    public static unsafe void Marshal(Node node, Vector3* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(Vector3.X), null), &objT->X, state);
        Marshal(node.GetAttributeValue(nameof(Vector3.Y), null), &objT->Y, state);
        Marshal(node.GetAttributeValue(nameof(Vector3.Z), null), &objT->Z, state);
    }

    public static unsafe void Marshal(Node node, Vector4* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(Vector4.X), null), &objT->X, state);
        Marshal(node.GetAttributeValue(nameof(Vector4.Y), null), &objT->Y, state);
        Marshal(node.GetAttributeValue(nameof(Vector4.Z), null), &objT->Z, state);
        Marshal(node.GetAttributeValue(nameof(Vector4.W), null), &objT->W, state);
    }

    public static unsafe void Marshal(Node node, Quaternion* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(Quaternion.X), null), &objT->X, state);
        Marshal(node.GetAttributeValue(nameof(Quaternion.Y), null), &objT->Y, state);
        Marshal(node.GetAttributeValue(nameof(Quaternion.Z), null), &objT->Z, state);
        Marshal(node.GetAttributeValue(nameof(Quaternion.W), null), &objT->W, state);
    }

    public static unsafe void Marshal(Node node, BoneInfluence* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(BoneInfluence.Weight), null), &objT->Weight, state);
        Marshal(node.GetAttributeValue(nameof(BoneInfluence.Bone), null), &objT->Bone, state);
    }

    public static unsafe void Marshal(Node node, Triangle* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(Triangle.V)), &objT->V, state);
        Marshal(node.GetChildNode(nameof(Triangle.Nrm), null), &objT->Nrm, state);
        Marshal(node.GetChildNode(nameof(Triangle.Dist), null), &objT->Dist, state);
    }

    public static unsafe void Marshal(Node node, BoxMinMax* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNode(nameof(BoxMinMax.Min), null), &objT->Min, state);
        Marshal(node.GetChildNode(nameof(BoxMinMax.Max), null), &objT->Max, state);
    }

    public static unsafe void Marshal(Node node, Sphere* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(Sphere.Radius), null), &objT->Radius, state);
        Marshal(node.GetChildNode(nameof(Sphere.Center), null), &objT->Center, state);
    }

    public static unsafe void Marshal(Node node, W3DMesh.MeshTriangles* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(W3DMesh.MeshTriangles.T)), &objT->T, state);
    }

    public static unsafe void Marshal(Node node, FXShaderConstant* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(FXShaderConstant.Name), null), &objT->Name, state);
    }

    public static unsafe void Marshal(Node node, FXShaderConstantBool* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNode(nameof(FXShaderConstantBool.Value), null), &objT->Value, state);
        Marshal(node, (FXShaderConstant*)objT, state);
    }

    public static unsafe void Marshal(Node node, FXShaderConstantFloat* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(FXShaderConstantFloat.Value)), &objT->Value, state);
        Marshal(node, (FXShaderConstant*)objT, state);
    }

    public static unsafe void Marshal(Node node, FXShaderConstantInt* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNode(nameof(FXShaderConstantInt.Value), null), &objT->Value, state);
        Marshal(node, (FXShaderConstant*)objT, state);
    }

    public static unsafe void Marshal(Node node, FXShaderConstantTexture* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNode(nameof(FXShaderConstantTexture.Value), null), &objT->Value, state);
        Marshal(node, (FXShaderConstant*)objT, state);
    }

    public static unsafe void Marshal(Node node, FXShaderConstant** objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        uint typeId = 0u;
        Marshal(node.GetAttributeValue("TypeId", "0"), &typeId, Tracker.NullTracker);
        switch (typeId)
        {
            case 0x89181982u:
                MarshalPolymorphicType<FXShaderConstantInt, FXShaderConstant>(node, objT, state);
                break;
            case 0xA3F84C3Du:
                MarshalPolymorphicType<FXShaderConstantBool, FXShaderConstant>(node, objT, state);
                break;
            case 0xA59096A6u:
                MarshalPolymorphicType<FXShaderConstantTexture, FXShaderConstant>(node, objT, state);
                break;
            case 0xDF08DF25u:
                MarshalPolymorphicType<FXShaderConstantFloat, FXShaderConstant>(node, objT, state);
                break;
            default:
                MarshalUnknownPolymorphicType(node, objT, state);
                break;
        }
    }

    public static unsafe void Marshal(Node node, FXShaderMaterial* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(FXShaderMaterial.ShaderName), null), &objT->ShaderName, state);
        Marshal(node.GetAttributeValue(nameof(FXShaderMaterial.TechniqueName), string.Empty), &objT->TechniqueName, state);
        Marshal(node.GetAttributeValue(nameof(FXShaderMaterial.TechniqueIndex), "0"), &objT->TechniqueIndex, state);
        Marshal(node.GetChildNode(nameof(FXShaderMaterial.Constants), null), &objT->Constants, state);
    }

    private static unsafe void Marshal(Node node, AABTree.TreePolyIndices* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(AABTree.TreePolyIndices.P)), &objT->P, state);
    }

    private static unsafe void Marshal(Node node, AABTree.TreeNode.NodeChild* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(AABTree.TreeNode.NodeChild.Front), null), &objT->Front, state);
        Marshal(node.GetAttributeValue(nameof(AABTree.TreeNode.NodeChild.Back), null), &objT->Back, state);
    }

    private static unsafe void Marshal(Node node, AABTree.TreeNode.NodeChild** objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        using Tracker.Context context = state.Push((void**)objT, (uint)sizeof(AABTree.TreeNode.NodeChild), 1u, typeof(AABTree.TreeNode.NodeChild));
        Marshal(node, *objT, state);
    }

    private static unsafe void Marshal(Node node, AABTree.TreeNode.NodePoly* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(AABTree.TreeNode.NodePoly.Begin), null), &objT->Begin, state);
        Marshal(node.GetAttributeValue(nameof(AABTree.TreeNode.NodePoly.Count), null), &objT->Count, state);
    }

    private static unsafe void Marshal(Node node, AABTree.TreeNode.NodePoly** objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        using Tracker.Context context = state.Push((void**)objT, (uint)sizeof(AABTree.TreeNode.NodePoly), 1u, typeof(AABTree.TreeNode.NodePoly));
        Marshal(node, *objT, state);
    }

    public static unsafe void Marshal(Node node, AABTree.TreeNode* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNode(nameof(AABTree.TreeNode.Min), null), &objT->Min, state);
        Marshal(node.GetChildNode(nameof(AABTree.TreeNode.Max), null), &objT->Max, state);
        Marshal(node.GetChildNode(nameof(AABTree.TreeNode.Children), null), &objT->Children, state);
        Marshal(node.GetChildNode(nameof(AABTree.TreeNode.Polys), null), &objT->Polys, state);
    }

    private static unsafe void Marshal(Node node, AABTree* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNode(nameof(AABTree.PolyIndices), null), &objT->PolyIndices, state);
        Marshal(node.GetChildNodes(nameof(AABTree.Node)), &objT->Node, state);
    }

    private static unsafe void Marshal(Node node, AABTree** objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        using Tracker.Context context = state.Push((void**)objT, (uint)sizeof(AABTree), 1u, typeof(AABTree));
        Marshal(node, *objT, state);
    }

    public static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.Vertex* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.Vertex.V)), &objT->V, state);
    }

    public static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.Normal* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.Normal.N)), &objT->N, state);
    }

    public static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.Tangent* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.Tangent.T)), &objT->T, state);
    }

    private static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.Tangent** objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        using Tracker.Context context = state.Push((void**)objT, (uint)sizeof(W3DMeshPipelineVertexData.Tangent), 1u, typeof(W3DMeshPipelineVertexData.Tangent));
        Marshal(node, *objT, state);
    }

    public static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.Binormal* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.Binormal.B)), &objT->B, state);
    }

    private static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.Binormal** objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        using Tracker.Context context = state.Push((void**)objT, (uint)sizeof(W3DMeshPipelineVertexData.Binormal), 1u, typeof(W3DMeshPipelineVertexData.Binormal));
        Marshal(node, *objT, state);
    }

    public static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.VertexColor* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.VertexColor.C)), &objT->C, state);
    }

    private static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.VertexColor** objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        using Tracker.Context context = state.Push((void**)objT, (uint)sizeof(W3DMeshPipelineVertexData.VertexColor), 1u, typeof(W3DMeshPipelineVertexData.VertexColor));
        Marshal(node, *objT, state);
    }

    public static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.TexCoord* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.TexCoord.T)), &objT->T, state);
    }

    public static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.DataBoneInfluence* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.DataBoneInfluence.I)), &objT->I, state);
    }

    public static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.ShadeIndex* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.ShadeIndex.I)), &objT->I, state);
    }

    private static unsafe void Marshal(Node node, W3DMeshPipelineVertexData.ShadeIndex** objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        using Tracker.Context context = state.Push((void**)objT, (uint)sizeof(W3DMeshPipelineVertexData.ShadeIndex), 1u, typeof(W3DMeshPipelineVertexData.ShadeIndex));
        Marshal(node, *objT, state);
    }

    private static unsafe void Marshal(Node node, W3DMeshMarshalerHelper* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        // Runtime (decompiled) form: write the shipped packed vertex data straight through — no re-packing — so a
        // decompiled W3DMesh reproduces its shipped bytes exactly (see Marshaler.W3DMeshRuntime). An absent
        // <VertexData> here means the shipped mesh had a null VertexData pointer; leave objT->VertexData null.
        if (IsRuntimeMesh(node))
        {
            Node vdNode = node.GetChildNode("VertexData", null);
            if (vdNode is not null)
            {
                using Tracker.Context context = state.Push(&objT->VertexData, (uint)sizeof(W3DMeshVertexData), 1u, typeof(W3DMeshVertexData));
                WriteRuntimeVertexData(vdNode, (W3DMeshVertexData*)objT->VertexData, state);
            }
            Marshal(node, (BaseRenderAssetType*)objT, state);
            return;
        }
        W3DMeshPipelineVertexData* pipelineData;
        using Tracker helperTracker = new Tracker((void**)&pipelineData, (uint)sizeof(W3DMeshPipelineVertexData), false, typeof(W3DMeshPipelineVertexData));
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.Vertices)), &pipelineData->Vertices, helperTracker);
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.Normals)), &pipelineData->Normals, helperTracker);
        Marshal(node.GetChildNode(nameof(W3DMeshPipelineVertexData.Tangents), null), &pipelineData->Tangents, helperTracker);
        Marshal(node.GetChildNode(nameof(W3DMeshPipelineVertexData.Binormals), null), &pipelineData->Binormals, helperTracker);
        Marshal(node.GetChildNode(nameof(W3DMeshPipelineVertexData.VertexColors), null), &pipelineData->VertexColors, helperTracker);
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.TexCoords)), &pipelineData->TexCoords, helperTracker);
        Marshal(node.GetChildNodes(nameof(W3DMeshPipelineVertexData.BoneInfluences)), &pipelineData->BoneInfluences, helperTracker);
        Marshal(node.GetChildNode(nameof(W3DMeshPipelineVertexData.ShadeIndices), null), &pipelineData->ShadeIndices, helperTracker);
        using (Tracker.Context context = state.Push(&objT->VertexData, (uint)sizeof(W3DMeshVertexData), 1u, typeof(W3DMeshVertexData)))
        {
            using W3DMeshProcessor processor = new W3DMeshProcessor();
            processor.BuildVertexData(pipelineData, (W3DMeshVertexData*)objT->VertexData, state);
        }
        Marshal(node, (BaseRenderAssetType*)objT, state);
    }

    public static unsafe void Marshal(Node node, W3DMesh* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(W3DMesh.Hidden), "false"), &objT->Hidden, state);
        Marshal(node.GetAttributeValue(nameof(W3DMesh.CastShadow), "false"), &objT->CastShadow, state);
        Marshal(node.GetAttributeValue(nameof(W3DMesh.GeometryType), null), &objT->GeometryType, state);
        Marshal(node.GetAttributeValue(nameof(W3DMesh.SortLevel), "0"), &objT->SortLevel, state);
        Marshal(node.GetChildNode(nameof(W3DMesh.BoundingBox), null), &objT->BoundingBox, state);
        Marshal(node.GetChildNode(nameof(W3DMesh.BoundingSphere), null), &objT->BoundingSphere, state);
        Marshal(node.GetChildNode(nameof(W3DMesh.Triangles), null), &objT->Triangles, state);
        Marshal(node.GetChildNode(nameof(W3DMesh.FXShader), null), &objT->FXShader, state);
        Marshal(node.GetChildNode(nameof(W3DMesh.AABTree), null), &objT->AABTree, state);
        Marshal(node, (W3DMeshMarshalerHelper*)objT, state);
    }

    // ---- W3DContainer / W3DHierarchy / W3DCollisionBox (finding 0019) --------------------------------------
    // Plain structural types: no lossy/typeless block, so these are ordinary field-by-field marshalers (the normal
    // pipeline), not a runtime pass-through. Field order follows the struct layout, matching EA's marshal order so
    // the appended variable-length data (strings) and the imports buffer are reproduced byte-exact.

    // SubObject: BoneIndex (attr), SubObjectID (attr, inline AnsiString), RenderObject (a reference-choice element
    // <RenderObject><Mesh|CollisionBox>name\idx</...></RenderObject>). The reference-resolution pass has already
    // rewritten the inner element's text to "name\index"; an element node's value is the concatenation of its
    // descendant text, so GetValue() on <RenderObject> yields that "name\index" directly — the AssetReference
    // marshaler parses the index from it without this code needing to name the choice members.
    public static unsafe void Marshal(Node node, SubObject* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(SubObject.BoneIndex), null), &objT->BoneIndex, state);
        Marshal(node.GetAttributeValue(nameof(SubObject.SubObjectID), string.Empty), &objT->SubObjectID, state);
        Marshal(node.GetChildNode(nameof(SubObject.RenderObject), null), &objT->RenderObject, state);
    }

    public static unsafe void Marshal(Node node, W3DContainer* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(W3DContainer.Hierarchy), null), &objT->Hierarchy, state);
        Marshal(node.GetChildNodes(nameof(W3DContainer.SubObject)), &objT->SubObject, state);
        Marshal(node, (BaseRenderAssetType*)objT, state);
    }

    public static unsafe void Marshal(Node node, W3DHierarchy.HierarchyPivot.Matrix* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M00), null), &objT->M00, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M10), null), &objT->M10, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M20), null), &objT->M20, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M30), null), &objT->M30, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M01), null), &objT->M01, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M11), null), &objT->M11, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M21), null), &objT->M21, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M31), null), &objT->M31, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M02), null), &objT->M02, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M12), null), &objT->M12, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M22), null), &objT->M22, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M32), null), &objT->M32, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M03), null), &objT->M03, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M13), null), &objT->M13, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M23), null), &objT->M23, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Matrix.M33), null), &objT->M33, state);
    }

    public static unsafe void Marshal(Node node, W3DHierarchy.HierarchyPivot* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Name), null), &objT->Name, state);
        Marshal(node.GetAttributeValue(nameof(W3DHierarchy.HierarchyPivot.Parent), null), &objT->Parent, state);
        Marshal(node.GetChildNode(nameof(W3DHierarchy.HierarchyPivot.Translation), null), &objT->Translation, state);
        Marshal(node.GetChildNode(nameof(W3DHierarchy.HierarchyPivot.Rotation), null), &objT->Rotation, state);
        Marshal(node.GetChildNode(nameof(W3DHierarchy.HierarchyPivot.FixupMatrix), null), &objT->FixupMatrix, state);
    }

    public static unsafe void Marshal(Node node, W3DHierarchy* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(W3DHierarchy.Pivot)), &objT->Pivot, state);
        Marshal(node, (BaseAssetType*)objT, state);
    }

    public static unsafe void Marshal(Node node, W3DCollisionBox* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(W3DCollisionBox.JoypadPickingOnly), "false"), &objT->JoypadPickingOnly, state);
        Marshal(node.GetChildNode(nameof(W3DCollisionBox.Center), null), &objT->Center, state);
        Marshal(node.GetChildNode(nameof(W3DCollisionBox.Extent), null), &objT->Extent, state);
        Marshal(node, (BaseRenderAssetType*)objT, state);
    }

    public static unsafe void Marshal(Node node, W3DAnimation.CompressionSetting* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(W3DAnimation.CompressionSetting.AllowTimeCoded), "true"), &objT->AllowTimeCoded, state);
        Marshal(node.GetAttributeValue(nameof(W3DAnimation.CompressionSetting.AllowAdaptiveDelta), "true"), &objT->AllowAdaptiveDelta, state);
        Marshal(node.GetAttributeValue(nameof(W3DAnimation.CompressionSetting.MaxTranslationError), "0.001"), &objT->MaxTranslationError, state);
        Marshal(node.GetAttributeValue(nameof(W3DAnimation.CompressionSetting.MaxRotationError), "0.01"), &objT->MaxRotationError, state);
        Marshal(node.GetAttributeValue(nameof(W3DAnimation.CompressionSetting.MaxVisibilityError), "0.01"), &objT->MaxVisibilityError, state);
        Marshal(node.GetAttributeValue(nameof(W3DAnimation.CompressionSetting.MaxAdaptiveDeltaError), "0.03"), &objT->MaxAdaptiveDeltaError, state);
        Marshal(node.GetAttributeValue(nameof(W3DAnimation.CompressionSetting.ForceReductionRate), "1.0"), &objT->ForceReductionRate, state);
    }

    public static unsafe void Marshal(Node node, W3DAnimation.CompressionSetting** objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        using Tracker.Context context = state.Push((void**)objT, (uint)sizeof(W3DAnimation.CompressionSetting), 1u, typeof(W3DAnimation.CompressionSetting));
        Marshal(node, *objT, state);
    }

    public static unsafe void Marshal(Node node, AnimationChannelBase* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(AnimationChannelBase.Pivot), null), &objT->Pivot, state);
        Marshal(node.GetAttributeValue(nameof(AnimationChannelBase.Type), null), &objT->Type, state);
        Marshal(node.GetAttributeValue(nameof(AnimationChannelBase.FirstFrame), null), &objT->FirstFrame, state);
    }

    public static unsafe void Marshal(Node node, AnimationChannelScalarFrame* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetValue(), &objT->Value, state);
        Marshal(node.GetAttributeValue(nameof(AnimationChannelScalarFrame.BinaryMove), "false"), &objT->BinaryMove, state);
    }

    public static unsafe void Marshal(Node node, AnimationChannelScalar* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(AnimationChannelScalar.Frame)), &objT->Frame, state);
        Marshal(node, (AnimationChannelBase*)objT, state);
    }

    public static unsafe void Marshal(Node node, AnimationChannelQuaternionFrame* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node, &objT->Value, state);
        Marshal(node.GetAttributeValue(nameof(AnimationChannelQuaternionFrame.BinaryMove), "false"), &objT->BinaryMove, state);
    }

    public static unsafe void Marshal(Node node, AnimationChannelQuaternion* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetChildNodes(nameof(AnimationChannelQuaternion.Frame)), &objT->Frame, state);
        Marshal(node, (AnimationChannelBase*)objT, state);
    }

    public static unsafe void Marshal(Node node, AnimationChannelBase** objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        uint typeId = 0u;
        Marshal(node.GetAttributeValue("TypeId", "0"), &typeId, Tracker.NullTracker);
        switch (typeId)
        {
            case 0x50D28EF5u:
                MarshalPolymorphicType<AnimationChannelScalar, AnimationChannelBase>(node, objT, state);
                break;
            case 0xF642DD20u:
                MarshalPolymorphicType<AnimationChannelQuaternion, AnimationChannelBase>(node, objT, state);
                break;
            default:
                MarshalUnknownPolymorphicType(node, objT, state);
                break;
        }
    }

    public static unsafe void Marshal(Node node, W3DAnimation* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        Marshal(node.GetAttributeValue(nameof(W3DAnimation.Hierarchy), null), &objT->Hierarchy, state);
        Marshal(node.GetAttributeValue(nameof(W3DAnimation.NumFrames), null), &objT->NumFrames, state);
        Marshal(node.GetAttributeValue(nameof(W3DAnimation.FrameRate), null), &objT->FrameRate, state);
        Marshal(node.GetChildNode(nameof(W3DAnimation.CompressionSettings), null), &objT->CompressionSettings, state);
        Marshal(node.GetChildNode(nameof(W3DAnimation.Channels), null), &objT->Channels, state);
        Marshal(node, (BaseAssetType*)objT, state);
    }
}