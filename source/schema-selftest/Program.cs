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

        public static int Main()
        {
            try
            {
                // Negative control: without augmentation the runtime channels MUST be rejected (else the test is
                // vacuous and would never notice a broken augmentation).
                List<string> before = Validate(Load(augment: false), RuntimeInstance);
                if (before.Count == 0)
                {
                    return Fail("negative control failed: the un-augmented schema accepted <Timecoded>/<Delta> — " +
                                "the test is vacuous (check the synthetic schema still models only ChannelScalar/Quaternion).");
                }

                // Positive: with augmentation the same instance MUST validate clean (the channels are now bound).
                List<string> after = Validate(Load(augment: true), RuntimeInstance);
                if (after.Count != 0)
                {
                    return Fail("augmentation did not bind the runtime channels — <Timecoded>/<Delta> still rejected " +
                                "under W3DAnimation/Channels:\n    " + string.Join("\n    ", after));
                }

                Console.WriteLine("schema-selftest: PASS — runtime W3DAnimation channels bind after augmentation " +
                                  "(and are rejected without it).");
                return 0;
            }
            catch (Exception ex)
            {
                return Fail("unexpected error: " + ex);
            }
        }

        private static XmlSchemaSet Load(bool augment)
        {
            XmlSchema schema;
            using (var reader = XmlReader.Create(new StringReader(SchemaXsd)))
            {
                schema = XmlSchema.Read(reader, null);
            }
            var set = new XmlSchemaSet();
            set.Add(schema);
            if (augment)
            {
                SchemaSet.AugmentRuntimeAnimationChannels(set);
            }
            set.Compile();
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
