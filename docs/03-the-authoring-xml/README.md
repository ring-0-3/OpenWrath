# 3 · The authoring XML

> **You'll understand:** the human-readable XML you actually *write* to describe or change an asset — the
> `AssetDeclaration` envelope, how `<Includes>` wires files together, how an asset's fields map to attributes
> and child elements, and the `inheritFrom` / `xai:joinAction` vocabulary that lets a 10-line file override a
> 100-field weapon.

## The source side of the same coin

Chapter 2 was about the **compiled** form — the stream, a linked bundle of serialized objects. This chapter is
the **source** form: the XML a human writes, which the compiler turns *into* a stream.

```
authoring XML  ──(compiler)──▶  asset stream (.manifest/.bin/.relo/.imp)
   (readable)                        (linked binary — chapter 2)
```

The XML is the readable description; the stream is the linked binary image. Modding happens in the XML, and
OpenWrath handles the trip between the two.

## XML in one minute (if it's new to you)

XML is just a **tree of tags**. There are only two kinds of information in it:

- **Elements** — tags like `<FiringDuration> … </FiringDuration>`, or self-closed `<FiringDuration … />`.
  Elements nest inside each other to form the tree.
- **Attributes** — the `key="value"` pairs *inside* a tag, like `MinSeconds="1.4s"`.

An element can carry attributes **and** hold child elements. That's the whole language. Kane's Wrath simply uses
this tree to describe game data — a weapon, a unit, an effect.

## The envelope: `<AssetDeclaration>`

Every KW asset file is exactly **one** `<AssetDeclaration>`. It's the envelope that says "here's a batch of
asset definitions," and everything else lives inside it:

```xml
<AssetDeclaration
    xmlns="uri:ea.com:eala:asset"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xi="http://www.w3.org/2001/XInclude"
    xmlns:xai="uri:ea.com:eala:asset:instance">
```

Those `xmlns:…` lines are **namespaces** — think of them as *vocabularies* the file switches on:

| Declaration | Vocabulary it enables |
|-------------|-----------------------|
| `xmlns="uri:ea.com:eala:asset"` | The **default** — EA's asset format. This is *why* `<WeaponTemplate>` and `<FiringDuration>` are recognized as asset elements at all. |
| `xmlns:xai="uri:ea.com:eala:asset:instance"` | The **override/merge** vocabulary — where `xai:joinAction` (`Append`, `Replace`, `Overwrite`, `Remove`) comes from. |
| `xmlns:xi="…/XInclude"` | Standard **XInclude**, for pulling file fragments in with `xi:include`. |
| `xmlns:xsi="…/XMLSchema-instance"` | The standard schema-typing namespace. |

In practice those four lines are fixed boilerplate at the top of every file — but now you know what each one
does, so none of it is mystery soup.

## `<Tags>` and `<Includes>`: wiring files together

Two standard children usually sit right inside the envelope:

```xml
    <Tags/>
    <Includes>
        <Include type="instance" source="DATA:GlobalData/Weapon.xml" />
    </Includes>
```

- **`<Tags/>`** — a small metadata container, usually empty (`/>` means "empty, self-closed").
- **`<Includes>` / `<Include …>`** — the **source-level import**. This is the authoring-side mirror of the
  stream's import table (chapter 2's `.imp`): where the compiled stream *links* to assets in other streams, the
  source *pulls in* other XML files so the compiler can **see** the things you reference. The `source="DATA:…"`
  path is relative to your SDK data root. You include `Weapon.xml` so that a reference to a weapon defined there
  — including an `inheritFrom` — can actually be resolved at compile time.

## An asset = fields (attributes) + sub-objects (child elements)

Inside the envelope you declare the asset itself. A weapon, for instance, carries:

- **scalar fields as attributes** — `AttackRange="350"`, `ClipSize="1"`, `CanFireWhileMoving="false"`;
- **structured or timed parts as child elements** — `<FiringDuration MinSeconds="2.8s" MaxSeconds="3.0s"/>`, a
  `<Nuggets>` list of what the shot does, and so on.

Which fields are attributes and which are child elements isn't arbitrary — it's fixed by the schema
(`CnC3Types.xsd`). When you inspect an asset (`openwrath inspect <name> --source`) you're reading exactly this
structure for the real, shipped definition.

## The modding superpower: `inheritFrom` + `joinAction`

Here's the idea that makes modding practical. To **change** an existing asset you do **not** rewrite it. You
declare it with the *same id*, inheriting from *itself*, and list only what you're changing:

```xml
<WeaponTemplate id="GDIMissileSoldierMissileLauncher"
                inheritFrom="GDIMissileSoldierMissileLauncher">
    <FiringDuration MinSeconds="1.4s" MaxSeconds="1.5s" />
</WeaponTemplate>
```

`id="X" inheritFrom="X"` reads as *"take the whole original asset X, then apply only the deltas I list."* The
compiler produces the **full** merged weapon — every original field intact — with just your one change applied.
That's why a tiny file can override a huge asset.

**`xai:joinAction`** controls *how* a child merges into the inherited asset — it matters most for **lists**:

- **`Append`** — add this element to a list (e.g. add a module to a GameObject's `<Behaviors>`). Give it an `id`
  so a re-bake merges by id instead of stacking duplicates.
- **`Replace` / `Overwrite`** — replace an existing element.
- **`Remove`** — delete an inherited element.

A singleton child like `<FiringDuration>` is simply overridden when you redeclare it (there can only be one). For
**lists**, the joiner matches elements by their `id` — see
[finding 0001](../findings/0001-joiner-matches-list-elements-by-id-only.md) for the exact rule and its sharp
edge (non-`id` elements *append* rather than replace).

## Worked example, annotated

The complete override that doubles the GDI Missile Squad's fire rate:

```xml
<?xml version="1.0" encoding="utf-8"?>
<AssetDeclaration                                      <!-- the envelope + its four vocabularies -->
    xmlns="uri:ea.com:eala:asset"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xi="http://www.w3.org/2001/XInclude"
    xmlns:xai="uri:ea.com:eala:asset:instance">

    <Tags/>
    <Includes>
        <!-- pull in the base weapon so inheritFrom can resolve it -->
        <Include type="instance" source="DATA:GlobalData/Weapon.xml" />
    </Includes>

    <!-- same id + inheritFrom itself = "the full original weapon, with only this changed" -->
    <WeaponTemplate id="GDIMissileSoldierMissileLauncher"
                    inheritFrom="GDIMissileSoldierMissileLauncher">
        <FiringDuration MinSeconds="1.4s" MaxSeconds="1.5s" />   <!-- was 2.8–3.0s -->
    </WeaponTemplate>

</AssetDeclaration>
```

Everything else about the weapon — its damage, range, projectile, sounds — comes along unchanged via
`inheritFrom`. You only ever write the delta.

## Recap

- Every file is one **`<AssetDeclaration>`** envelope; its `xmlns:…` lines switch on the asset, override,
  and include vocabularies.
- **`<Includes>`** is the source-level import — it pulls in other XML so references and `inheritFrom` resolve
  (the authoring mirror of the stream's `.imp` table).
- An asset's **attributes are its scalar fields**; its **child elements are its structured/timed sub-parts**;
  the schema decides which is which.
- To change an asset, declare it with the **same `id` + `inheritFrom` itself** and list only the delta;
  **`xai:joinAction`** controls how children merge into lists.

---

Previous: [2 · Asset streams](../02-asset-streams/README.md) ·
Next: *references and the import graph (coming)*
