using System;
using System.Collections.Generic;
using System.IO;
using System.Xml;
using System.Xml.Schema;
using BinaryAssetBuilder.Core.SageXml;

namespace BinaryAssetBuilder.SchemaSelfTest
{
    // Durable, CI-runnable guard for SchemaSet.AugmentRuntimeAnimationChannels (finding 0014). The silent break
    // of exactly this mechanism — the runtime W3DAnimation channels not being schema-bound — is what caused the
    // whole detour and a "Critical: Element Timecoded ... doesn't have a schema type" at compile time. The
    // byte-exact round-trip would also catch it, but that needs game data and a full build; this catches a
    // regression with NO game data, in CI, using only a tiny synthetic schema and the BCL XSD validator.
    //
    // It asserts the OBSERVABLE invariant (not an implementation detail): after augmentation, <Timecoded>/<Delta>
    // are accepted under W3DAnimation/Channels; and a negative control proves the un-augmented schema rejects
    // them, so the test can never pass vacuously.
    public static class Program
    {
        private const string Ns = "uri:ea.com:eala:asset";

        // Minimal schema mirroring the shape the augmentation navigates: W3DAnimation (complexContent extension,
        // a <Channels> element with an inline complexType whose particle is a choice of the AUTHORING channels),
        // plus EA's runtime channel types that the augmentation binds to. Nothing here is EA content — it is a
        // hand-written structural stand-in.
        private const string SchemaXsd = @"<?xml version='1.0'?>
<xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema'
           targetNamespace='uri:ea.com:eala:asset'
           xmlns='uri:ea.com:eala:asset'
           elementFormDefault='qualified'>
  <xs:complexType name='BaseAssetType'/>
  <xs:complexType name='AnimationChannelBaseRuntime'>
    <xs:attribute name='Pivot' type='xs:unsignedShort'/>
  </xs:complexType>
  <xs:complexType name='AnimationChannelTimecoded'>
    <xs:complexContent><xs:extension base='AnimationChannelBaseRuntime'/></xs:complexContent>
  </xs:complexType>
  <xs:complexType name='AnimationChannelDelta'>
    <xs:complexContent><xs:extension base='AnimationChannelBaseRuntime'/></xs:complexContent>
  </xs:complexType>
  <xs:complexType name='AnimationChannelScalar'/>
  <xs:complexType name='AnimationChannelQuaternion'/>
  <xs:complexType name='W3DAnimation'>
    <xs:complexContent>
      <xs:extension base='BaseAssetType'>
        <xs:sequence>
          <xs:element name='Channels'>
            <xs:complexType>
              <xs:choice minOccurs='0' maxOccurs='unbounded'>
                <xs:element name='ChannelScalar' type='AnimationChannelScalar'/>
                <xs:element name='ChannelQuaternion' type='AnimationChannelQuaternion'/>
              </xs:choice>
            </xs:complexType>
          </xs:element>
        </xs:sequence>
      </xs:extension>
    </xs:complexContent>
  </xs:complexType>
  <xs:element name='W3DAnimation' type='W3DAnimation'/>
</xs:schema>";

        // A runtime-form animation: <Timecoded>/<Delta> channels, which the AUTHORING schema does not reach.
        private const string RuntimeInstance =
            "<W3DAnimation xmlns='uri:ea.com:eala:asset'><Channels>" +
            "<Timecoded Pivot='1'/><Delta Pivot='2'/>" +
            "</Channels></W3DAnimation>";

        // Minimal schema mirroring the shape AugmentRuntimeMeshVertexData navigates: W3DMesh (complexContent
        // extension) whose sequence has a REQUIRED authoring <Vertices> group and no element for the packed vertex
        // data. Nothing here is EA content — a hand-written structural stand-in.
        private const string MeshSchemaXsd = @"<?xml version='1.0'?>
<xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema'
           targetNamespace='uri:ea.com:eala:asset'
           xmlns='uri:ea.com:eala:asset'
           elementFormDefault='qualified'>
  <xs:complexType name='BaseRenderAssetType'/>
  <xs:complexType name='W3DMesh'>
    <xs:complexContent>
      <xs:extension base='BaseRenderAssetType'>
        <xs:sequence>
          <xs:element name='Vertices'>
            <xs:complexType>
              <xs:sequence><xs:element name='V' type='xs:string' maxOccurs='unbounded'/></xs:sequence>
            </xs:complexType>
          </xs:element>
        </xs:sequence>
      </xs:extension>
    </xs:complexContent>
  </xs:complexType>
  <xs:element name='W3DMesh' type='W3DMesh'/>
</xs:schema>";

        // A runtime-form mesh: a packed <VertexData> and NO authoring <Vertices>, which the authoring schema
        // neither declares (VertexData) nor permits (Vertices is required).
        private const string RuntimeMeshInstance =
            "<W3DMesh xmlns='uri:ea.com:eala:asset'>" +
            "<VertexData NumVertices='4' VertexStride='32'>" +
            "<VertexElementData>AAAA</VertexElementData><VertexDeclaration>AAAA</VertexDeclaration><Bones></Bones>" +
            "</VertexData></W3DMesh>";

        // Minimal schema mirroring the shape AugmentRuntimeTexturePayload navigates: Texture (complexContent
        // extension) whose content sequence is EMPTY and whose fields are pipelineOnly directives (here just a File
        // attribute), with no element for the packed DDS payload. Nothing here is EA content — a hand-written
        // structural stand-in.
        private const string TextureSchemaXsd = @"<?xml version='1.0'?>
<xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema'
           targetNamespace='uri:ea.com:eala:asset'
           xmlns='uri:ea.com:eala:asset'
           elementFormDefault='qualified'>
  <xs:complexType name='BaseAssetType'/>
  <xs:complexType name='Texture'>
    <xs:complexContent>
      <xs:extension base='BaseAssetType'>
        <xs:sequence/>
        <xs:attribute name='File' type='xs:string'/>
      </xs:extension>
    </xs:complexContent>
  </xs:complexType>
  <xs:element name='Texture' type='Texture'/>
</xs:schema>";

        // A runtime-form texture: a pass-through <Payload> (base64 DDS) and no authoring attributes, which the
        // authoring schema's empty sequence does not permit.
        private const string RuntimeTextureInstance =
            "<Texture xmlns='uri:ea.com:eala:asset'><Payload>AAAA</Payload></Texture>";

        public static int Main()
        {
            try
            {
                int rc = TestAnimation();
                if (rc != 0)
                {
                    return rc;
                }
                rc = TestMesh();
                if (rc != 0)
                {
                    return rc;
                }
                return TestTexture();
            }
            catch (Exception ex)
            {
                return Fail("unexpected error: " + ex);
            }
        }

        private static int TestAnimation()
        {
            // Negative control: without augmentation the runtime channels MUST be rejected (else the test is
            // vacuous and would never notice a broken augmentation).
            List<string> before = Validate(LoadAnimation(augment: false), RuntimeInstance);
            if (before.Count == 0)
            {
                return Fail("negative control failed: the un-augmented schema accepted <Timecoded>/<Delta> — " +
                            "the test is vacuous (check the synthetic schema still models only ChannelScalar/Quaternion).");
            }

            // Positive: with augmentation the same instance MUST validate clean (the channels are now bound).
            List<string> after = Validate(LoadAnimation(augment: true), RuntimeInstance);
            if (after.Count != 0)
            {
                return Fail("augmentation did not bind the runtime channels — <Timecoded>/<Delta> still rejected " +
                            "under W3DAnimation/Channels:\n    " + string.Join("\n    ", after));
            }

            Console.WriteLine("schema-selftest: PASS — runtime W3DAnimation channels bind after augmentation " +
                              "(and are rejected without it).");
            return 0;
        }

        private static int TestMesh()
        {
            // NOTE (same caveat as TestAnimation): this guards the augmentation LOGIC against a synthetic schema
            // shape, not the real KW schema. Both augmenters no-op when the live schema doesn't match the expected
            // shape, so if EA's W3DMesh shape ever drifted this test would stay green while the real binding
            // silently stopped firing — only the byte-exact round-trip (needs game data) catches that.
            // Negative control: without augmentation the packed <VertexData> form MUST be rejected.
            List<string> before = Validate(LoadMesh(augment: false), RuntimeMeshInstance);
            if (before.Count == 0)
            {
                return Fail("negative control failed: the un-augmented mesh schema accepted the packed <VertexData> " +
                            "form — the test is vacuous (check <Vertices> is still required and <VertexData> undeclared).");
            }

            // Positive: with augmentation the runtime mesh MUST validate clean.
            List<string> after = Validate(LoadMesh(augment: true), RuntimeMeshInstance);
            if (after.Count != 0)
            {
                return Fail("augmentation did not bind the runtime vertex data — the packed <VertexData> form is still " +
                            "rejected under W3DMesh:\n    " + string.Join("\n    ", after));
            }

            Console.WriteLine("schema-selftest: PASS — runtime W3DMesh <VertexData> binds after augmentation " +
                              "(and is rejected without it).");
            return 0;
        }

        private static int TestTexture()
        {
            // NOTE (same caveat as TestMesh): guards the augmentation LOGIC against a synthetic schema shape, not the
            // real KW schema; the augmenter no-ops when the live schema doesn't match, so a shape drift would keep
            // this green while the real binding silently stopped firing — only the byte-exact round-trip catches that.
            // Negative control: without augmentation the pass-through <Payload> MUST be rejected (empty sequence).
            List<string> before = Validate(LoadTexture(augment: false), RuntimeTextureInstance);
            if (before.Count == 0)
            {
                return Fail("negative control failed: the un-augmented texture schema accepted the pass-through " +
                            "<Payload> form — the test is vacuous (check the Texture content sequence is still empty).");
            }

            // Positive: with augmentation the runtime texture MUST validate clean.
            List<string> after = Validate(LoadTexture(augment: true), RuntimeTextureInstance);
            if (after.Count != 0)
            {
                return Fail("augmentation did not bind the runtime texture payload — the pass-through <Payload> form " +
                            "is still rejected under Texture:\n    " + string.Join("\n    ", after));
            }

            Console.WriteLine("schema-selftest: PASS — runtime Texture <Payload> binds after augmentation " +
                              "(and is rejected without it).");
            return 0;
        }

        private static XmlSchemaSet LoadTexture(bool augment)
        {
            XmlSchemaSet set = LoadSet(TextureSchemaXsd);
            if (augment)
            {
                SchemaSet.AugmentRuntimeTexturePayload(set);
            }
            set.Compile();
            return set;
        }

        private static XmlSchemaSet LoadAnimation(bool augment)
        {
            XmlSchemaSet set = LoadSet(SchemaXsd);
            if (augment)
            {
                SchemaSet.AugmentRuntimeAnimationChannels(set);
            }
            set.Compile();
            return set;
        }

        private static XmlSchemaSet LoadMesh(bool augment)
        {
            XmlSchemaSet set = LoadSet(MeshSchemaXsd);
            if (augment)
            {
                SchemaSet.AugmentRuntimeMeshVertexData(set);
            }
            set.Compile();
            return set;
        }

        private static XmlSchemaSet LoadSet(string xsd)
        {
            XmlSchema schema;
            using (var reader = XmlReader.Create(new StringReader(xsd)))
            {
                schema = XmlSchema.Read(reader, null);
            }
            var set = new XmlSchemaSet();
            set.Add(schema);
            return set;
        }

        private static List<string> Validate(XmlSchemaSet schemas, string instanceXml)
        {
            var errors = new List<string>();
            var settings = new XmlReaderSettings { ValidationType = ValidationType.Schema };
            settings.Schemas = schemas;
            settings.ValidationEventHandler += (_, e) => errors.Add(e.Message);
            using var reader = XmlReader.Create(new StringReader(instanceXml), settings);
            while (reader.Read()) { }
            return errors;
        }

        private static int Fail(string message)
        {
            Console.Error.WriteLine("schema-selftest: FAIL — " + message);
            return 1;
        }
    }
}
