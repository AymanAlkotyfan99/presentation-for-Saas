// generated/presentation-document.ts
var PRESENTATION_DOCUMENT_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.bayanly.com/presentation-document/v1.schema.json",
  "title": "Bayanly Presentation Document v1",
  "description": "Renderer-independent canonical presentation authoring document.",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "schemaVersion": {
      "const": "1.0.0"
    },
    "documentId": {
      "type": "string",
      "format": "uuid"
    },
    "presentationId": {
      "type": "string",
      "format": "uuid"
    },
    "title": {
      "type": "string",
      "minLength": 1,
      "maxLength": 512,
      "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
    },
    "locale": {
      "$ref": "#/$defs/locale"
    },
    "baseDirection": {
      "$ref": "#/$defs/direction"
    },
    "aspectRatio": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "width": {
          "type": "number",
          "exclusiveMinimum": 0,
          "maximum": 100
        },
        "height": {
          "type": "number",
          "exclusiveMinimum": 0,
          "maximum": 100
        }
      },
      "required": [
        "width",
        "height"
      ]
    },
    "theme": {
      "$ref": "#/$defs/theme"
    },
    "fontPolicy": {
      "$ref": "#/$defs/fontPolicy"
    },
    "metadata": {
      "$ref": "#/$defs/documentMetadata"
    },
    "slides": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/slide"
      },
      "minItems": 1,
      "maxItems": 200
    },
    "assets": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/asset"
      },
      "minItems": 0,
      "maxItems": 2e3
    },
    "exportHints": {
      "$ref": "#/$defs/exportHints"
    },
    "compatibility": {
      "$ref": "#/$defs/documentCompatibility"
    },
    "extensions": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/extension"
      },
      "minItems": 0,
      "maxItems": 64
    }
  },
  "required": [
    "schemaVersion",
    "documentId",
    "presentationId",
    "title",
    "locale",
    "baseDirection",
    "aspectRatio",
    "theme",
    "fontPolicy",
    "metadata",
    "slides",
    "assets",
    "exportHints",
    "compatibility"
  ],
  "$defs": {
    "locale": {
      "type": "string",
      "enum": [
        "en",
        "ar"
      ]
    },
    "direction": {
      "type": "string",
      "enum": [
        "ltr",
        "rtl",
        "auto"
      ]
    },
    "logicalAlignment": {
      "type": "string",
      "enum": [
        "start",
        "center",
        "end",
        "justify"
      ]
    },
    "color": {
      "type": "string",
      "pattern": "^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$"
    },
    "stableReference": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    },
    "geometry": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "x": {
          "type": "number",
          "minimum": -5120,
          "maximum": 5120
        },
        "y": {
          "type": "number",
          "minimum": -2880,
          "maximum": 2880
        },
        "width": {
          "type": "number",
          "exclusiveMinimum": 0,
          "maximum": 5120
        },
        "height": {
          "type": "number",
          "exclusiveMinimum": 0,
          "maximum": 2880
        },
        "anchor": {
          "type": "string",
          "enum": [
            "top-start",
            "top-center",
            "top-end",
            "center",
            "bottom-start",
            "bottom-center",
            "bottom-end"
          ]
        }
      },
      "required": [
        "x",
        "y",
        "width",
        "height"
      ]
    },
    "transform": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "rotation": {
          "type": "number",
          "minimum": -360,
          "maximum": 360
        },
        "flipHorizontal": {
          "type": "boolean"
        },
        "flipVertical": {
          "type": "boolean"
        }
      },
      "required": []
    },
    "stroke": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "color": {
          "$ref": "#/$defs/color"
        },
        "width": {
          "type": "number",
          "minimum": 0,
          "maximum": 100
        },
        "opacity": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        },
        "dash": {
          "type": "array",
          "items": {
            "type": "number",
            "minimum": 0,
            "maximum": 1e3
          },
          "minItems": 0,
          "maxItems": 32
        }
      },
      "required": [
        "color",
        "width"
      ]
    },
    "shadow": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "color": {
          "$ref": "#/$defs/color"
        },
        "blur": {
          "type": "number",
          "minimum": 0,
          "maximum": 500
        },
        "offsetX": {
          "type": "number",
          "minimum": -1e3,
          "maximum": 1e3
        },
        "offsetY": {
          "type": "number",
          "minimum": -1e3,
          "maximum": 1e3
        },
        "opacity": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        }
      },
      "required": [
        "color"
      ]
    },
    "style": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "opacity": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        },
        "fill": {
          "$ref": "#/$defs/color"
        },
        "stroke": {
          "$ref": "#/$defs/stroke"
        },
        "shadow": {
          "$ref": "#/$defs/shadow"
        },
        "cornerRadius": {
          "type": "number",
          "minimum": 0,
          "maximum": 2e3
        }
      },
      "required": []
    },
    "accessibility": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "label": {
          "type": "string",
          "minLength": 1,
          "maxLength": 512,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "description": {
          "type": "string",
          "minLength": 0,
          "maxLength": 2048,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "decorative": {
          "type": "boolean"
        }
      },
      "required": []
    },
    "elementCompatibility": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "source": {
          "type": "string",
          "enum": [
            "v1",
            "v2",
            "template",
            "canonical"
          ]
        },
        "legacyId": {
          "type": "string",
          "minLength": 0,
          "maxLength": 128,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "sourceLayoutRef": {
          "$ref": "#/$defs/stableReference"
        },
        "warnings": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/stableReference"
          },
          "minItems": 0,
          "maxItems": 64
        }
      },
      "required": []
    },
    "hyperlink": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "kind": {
          "type": "string",
          "enum": [
            "external",
            "asset"
          ]
        },
        "href": {
          "type": "string",
          "minLength": 9,
          "maxLength": 2048,
          "format": "uri",
          "pattern": "^https://(?!localhost(?:[:/]|$)|127\\.|10\\.|192\\.168\\.|169\\.254\\.|172\\.(?:1[6-9]|2[0-9]|3[01])\\.)"
        },
        "assetId": {
          "type": "string",
          "format": "uuid"
        }
      },
      "required": [
        "kind"
      ]
    },
    "textRun": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "text": {
          "type": "string",
          "minLength": 0,
          "maxLength": 1e5,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "language": {
          "type": "string",
          "minLength": 2,
          "maxLength": 35,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "fontFamilyRef": {
          "$ref": "#/$defs/stableReference"
        },
        "fontWeight": {
          "type": "integer",
          "minimum": 100,
          "maximum": 900,
          "multipleOf": 100
        },
        "fontStyle": {
          "type": "string",
          "enum": [
            "normal",
            "italic"
          ]
        },
        "decorations": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "underline",
              "line-through"
            ]
          },
          "minItems": 0,
          "maxItems": 2
        },
        "fontSize": {
          "type": "number",
          "exclusiveMinimum": 0,
          "maximum": 512
        },
        "color": {
          "$ref": "#/$defs/color"
        },
        "lineHeight": {
          "type": "number",
          "minimum": 0.5,
          "maximum": 10
        },
        "letterSpacing": {
          "type": "number",
          "minimum": -100,
          "maximum": 100
        },
        "hyperlink": {
          "$ref": "#/$defs/hyperlink"
        }
      },
      "required": [
        "id",
        "text"
      ]
    },
    "listIntent": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "kind": {
          "type": "string",
          "enum": [
            "bullet",
            "number"
          ]
        },
        "level": {
          "type": "integer",
          "minimum": 0,
          "maximum": 8
        },
        "start": {
          "type": "integer",
          "minimum": 1,
          "maximum": 1e5
        }
      },
      "required": [
        "kind",
        "level"
      ]
    },
    "paragraph": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "direction": {
          "$ref": "#/$defs/direction"
        },
        "logicalAlignment": {
          "$ref": "#/$defs/logicalAlignment"
        },
        "list": {
          "$ref": "#/$defs/listIntent"
        },
        "runs": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/textRun"
          },
          "minItems": 1,
          "maxItems": 1e4
        }
      },
      "required": [
        "id",
        "direction",
        "logicalAlignment",
        "runs"
      ]
    },
    "crop": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "x": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        },
        "y": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        },
        "width": {
          "type": "number",
          "exclusiveMinimum": 0,
          "maximum": 1
        },
        "height": {
          "type": "number",
          "exclusiveMinimum": 0,
          "maximum": 1
        },
        "focalX": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        },
        "focalY": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        }
      },
      "required": [
        "x",
        "y",
        "width",
        "height"
      ]
    },
    "point": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "x": {
          "type": "number",
          "minimum": -5120,
          "maximum": 5120
        },
        "y": {
          "type": "number",
          "minimum": -2880,
          "maximum": 2880
        }
      },
      "required": [
        "x",
        "y"
      ]
    },
    "tableCell": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "paragraphs": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/paragraph"
          },
          "minItems": 1,
          "maxItems": 100
        },
        "columnSpan": {
          "type": "integer",
          "minimum": 1,
          "maximum": 50
        },
        "rowSpan": {
          "type": "integer",
          "minimum": 1,
          "maximum": 100
        },
        "background": {
          "$ref": "#/$defs/color"
        }
      },
      "required": [
        "paragraphs"
      ]
    },
    "tableRow": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "cells": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/tableCell"
          },
          "minItems": 1,
          "maxItems": 50
        }
      },
      "required": [
        "cells"
      ]
    },
    "chartSeries": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "name": {
          "type": "string",
          "minLength": 1,
          "maxLength": 512,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "values": {
          "type": "array",
          "items": {
            "type": "number",
            "minimum": -1e12,
            "maximum": 1e12
          },
          "minItems": 1,
          "maxItems": 5e3
        },
        "color": {
          "$ref": "#/$defs/color"
        }
      },
      "required": [
        "id",
        "name",
        "values"
      ]
    },
    "textElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "text"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "paragraphs": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/paragraph"
          },
          "minItems": 1,
          "maxItems": 1e3
        },
        "verticalAlignment": {
          "type": "string",
          "enum": [
            "top",
            "middle",
            "bottom"
          ]
        },
        "overflow": {
          "type": "string",
          "enum": [
            "clip",
            "ellipsis",
            "shrink"
          ]
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder",
        "paragraphs"
      ]
    },
    "imageElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "image"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "assetId": {
          "type": "string",
          "format": "uuid"
        },
        "fit": {
          "type": "string",
          "enum": [
            "contain",
            "cover",
            "fill"
          ]
        },
        "crop": {
          "$ref": "#/$defs/crop"
        },
        "altText": {
          "type": "string",
          "minLength": 0,
          "maxLength": 2048,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder",
        "assetId",
        "fit"
      ]
    },
    "shapeElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "shape"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "shapeKind": {
          "type": "string",
          "enum": [
            "rectangle",
            "rounded-rectangle",
            "ellipse",
            "triangle",
            "diamond"
          ]
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder",
        "shapeKind"
      ]
    },
    "lineElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "line"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "points": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/point"
          },
          "minItems": 2,
          "maxItems": 1e3
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder",
        "points"
      ]
    },
    "arrowElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "arrow"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "points": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/point"
          },
          "minItems": 2,
          "maxItems": 1e3
        },
        "head": {
          "type": "string",
          "enum": [
            "start",
            "end",
            "both"
          ]
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder",
        "points",
        "head"
      ]
    },
    "vectorElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "vector"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "points": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/point"
          },
          "minItems": 2,
          "maxItems": 1e4
        },
        "closed": {
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder",
        "points",
        "closed"
      ]
    },
    "iconElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "icon"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "assetId": {
          "type": "string",
          "format": "uuid"
        },
        "iconName": {
          "$ref": "#/$defs/stableReference"
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder"
      ]
    },
    "tableElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "table"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "rows": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/tableRow"
          },
          "minItems": 1,
          "maxItems": 100
        },
        "headerRows": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder",
        "rows"
      ]
    },
    "chartElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "chart"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "chartId": {
          "type": "string",
          "format": "uuid"
        },
        "chartType": {
          "type": "string",
          "enum": [
            "area",
            "bar",
            "bubble",
            "donut",
            "horizontal-bar",
            "line",
            "pie",
            "polar-area",
            "radar",
            "scatter",
            "stacked-bar"
          ]
        },
        "categoryLabels": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 0,
            "maxLength": 512,
            "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
          },
          "minItems": 0,
          "maxItems": 5e3
        },
        "series": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/chartSeries"
          },
          "minItems": 1,
          "maxItems": 100
        },
        "title": {
          "type": "string",
          "minLength": 0,
          "maxLength": 1024,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder",
        "chartId",
        "chartType",
        "series"
      ]
    },
    "containerElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "container"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "layoutIntent": {
          "type": "string",
          "enum": [
            "free",
            "row",
            "column",
            "grid",
            "stack"
          ]
        },
        "children": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/element"
          },
          "minItems": 0,
          "maxItems": 500
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder",
        "layoutIntent",
        "children"
      ]
    },
    "groupElement": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "type": {
          "const": "group"
        },
        "geometry": {
          "$ref": "#/$defs/geometry"
        },
        "transform": {
          "$ref": "#/$defs/transform"
        },
        "style": {
          "$ref": "#/$defs/style"
        },
        "accessibility": {
          "$ref": "#/$defs/accessibility"
        },
        "zOrder": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1e5
        },
        "locked": {
          "type": "boolean"
        },
        "hidden": {
          "type": "boolean"
        },
        "compatibility": {
          "$ref": "#/$defs/elementCompatibility"
        },
        "children": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/element"
          },
          "minItems": 1,
          "maxItems": 500
        }
      },
      "required": [
        "id",
        "type",
        "geometry",
        "zOrder",
        "children"
      ]
    },
    "element": {
      "oneOf": [
        {
          "$ref": "#/$defs/textElement"
        },
        {
          "$ref": "#/$defs/imageElement"
        },
        {
          "$ref": "#/$defs/shapeElement"
        },
        {
          "$ref": "#/$defs/lineElement"
        },
        {
          "$ref": "#/$defs/arrowElement"
        },
        {
          "$ref": "#/$defs/vectorElement"
        },
        {
          "$ref": "#/$defs/iconElement"
        },
        {
          "$ref": "#/$defs/tableElement"
        },
        {
          "$ref": "#/$defs/chartElement"
        },
        {
          "$ref": "#/$defs/containerElement"
        },
        {
          "$ref": "#/$defs/groupElement"
        }
      ]
    },
    "speakerNotes": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "locale": {
          "$ref": "#/$defs/locale"
        },
        "direction": {
          "$ref": "#/$defs/direction"
        },
        "paragraphs": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/paragraph"
          },
          "minItems": 0,
          "maxItems": 1e3
        }
      },
      "required": [
        "id",
        "locale",
        "direction",
        "paragraphs"
      ]
    },
    "slideBackground": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "color": {
          "$ref": "#/$defs/color"
        },
        "assetId": {
          "type": "string",
          "format": "uuid"
        }
      },
      "required": []
    },
    "slideCompatibility": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "legacySlideId": {
          "type": "string",
          "minLength": 0,
          "maxLength": 128,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "legacyLayoutGroup": {
          "type": "string",
          "minLength": 0,
          "maxLength": 128,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "legacyLayout": {
          "type": "string",
          "minLength": 0,
          "maxLength": 128,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "requiresLegacyRenderer": {
          "type": "boolean"
        },
        "warnings": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/stableReference"
          },
          "minItems": 0,
          "maxItems": 128
        }
      },
      "required": []
    },
    "slide": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "order": {
          "type": "integer",
          "minimum": 0,
          "maximum": 199
        },
        "title": {
          "type": "string",
          "minLength": 0,
          "maxLength": 512,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "semanticRole": {
          "type": "string",
          "enum": [
            "title",
            "content",
            "section",
            "table-of-contents",
            "closing",
            "other"
          ]
        },
        "background": {
          "$ref": "#/$defs/slideBackground"
        },
        "layoutIntent": {
          "type": "string",
          "enum": [
            "free",
            "row",
            "column",
            "grid",
            "stack",
            "template"
          ]
        },
        "elements": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/element"
          },
          "minItems": 0,
          "maxItems": 500
        },
        "speakerNotes": {
          "$ref": "#/$defs/speakerNotes"
        },
        "locale": {
          "$ref": "#/$defs/locale"
        },
        "direction": {
          "$ref": "#/$defs/direction"
        },
        "transitionHint": {
          "type": "string",
          "enum": [
            "none",
            "fade",
            "push"
          ]
        },
        "exportCapabilities": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "raster",
              "pdf",
              "editable-text",
              "notes",
              "requires-fallback"
            ]
          },
          "minItems": 0,
          "maxItems": 5
        },
        "compatibility": {
          "$ref": "#/$defs/slideCompatibility"
        }
      },
      "required": [
        "id",
        "order",
        "layoutIntent",
        "elements"
      ]
    },
    "assetMetadata": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "width": {
          "type": "integer",
          "minimum": 1,
          "maximum": 1e5
        },
        "height": {
          "type": "integer",
          "minimum": 1,
          "maximum": 1e5
        },
        "byteSize": {
          "type": "integer",
          "minimum": 0,
          "maximum": 2e9
        },
        "sha256": {
          "type": "string",
          "pattern": "^[a-f0-9]{64}$"
        },
        "originalName": {
          "type": "string",
          "minLength": 0,
          "maxLength": 255,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        }
      },
      "required": []
    },
    "asset": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "assetId": {
          "type": "string",
          "format": "uuid"
        },
        "kind": {
          "type": "string",
          "enum": [
            "image",
            "icon",
            "font"
          ]
        },
        "mimeType": {
          "type": "string",
          "enum": [
            "image/png",
            "image/jpeg",
            "image/webp",
            "image/gif",
            "font/ttf",
            "font/otf",
            "font/woff",
            "font/woff2"
          ]
        },
        "sourceType": {
          "type": "string",
          "enum": [
            "uploaded",
            "generated",
            "stock",
            "template",
            "legacy"
          ]
        },
        "role": {
          "type": "string",
          "enum": [
            "content",
            "background",
            "logo",
            "decoration",
            "icon",
            "font"
          ]
        },
        "metadata": {
          "$ref": "#/$defs/assetMetadata"
        }
      },
      "required": [
        "assetId",
        "kind",
        "mimeType",
        "sourceType",
        "role"
      ]
    },
    "themeToken": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "name": {
          "$ref": "#/$defs/stableReference"
        },
        "value": {
          "$ref": "#/$defs/color"
        }
      },
      "required": [
        "name",
        "value"
      ]
    },
    "theme": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "themeRef": {
          "$ref": "#/$defs/stableReference"
        },
        "revisionRef": {
          "$ref": "#/$defs/stableReference"
        },
        "colorTokens": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/themeToken"
          },
          "minItems": 0,
          "maxItems": 128
        },
        "spacingScale": {
          "type": "array",
          "items": {
            "type": "number",
            "minimum": 0,
            "maximum": 1e3
          },
          "minItems": 0,
          "maxItems": 64
        },
        "defaultBackground": {
          "$ref": "#/$defs/color"
        }
      },
      "required": [
        "themeRef",
        "colorTokens"
      ]
    },
    "fontFamily": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id": {
          "$ref": "#/$defs/stableReference"
        },
        "family": {
          "type": "string",
          "minLength": 1,
          "maxLength": 128,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "fallbacks": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 128,
            "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
          },
          "minItems": 0,
          "maxItems": 16
        },
        "assetId": {
          "type": "string",
          "format": "uuid"
        }
      },
      "required": [
        "id",
        "family",
        "fallbacks"
      ]
    },
    "fontPolicy": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "families": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/fontFamily"
          },
          "minItems": 0,
          "maxItems": 128
        },
        "defaultBodyRef": {
          "$ref": "#/$defs/stableReference"
        },
        "defaultHeadingRef": {
          "$ref": "#/$defs/stableReference"
        },
        "allowSystemFallback": {
          "type": "boolean"
        }
      },
      "required": [
        "families",
        "allowSystemFallback"
      ]
    },
    "documentMetadata": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "description": {
          "type": "string",
          "minLength": 0,
          "maxLength": 4096,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "tags": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 128,
            "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
          },
          "minItems": 0,
          "maxItems": 100
        },
        "authoringIntent": {
          "type": "string",
          "enum": [
            "generated",
            "edited",
            "imported",
            "template-derived"
          ]
        },
        "sourceApplicationVersion": {
          "type": "string",
          "minLength": 0,
          "maxLength": 64,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        }
      },
      "required": []
    },
    "exportHints": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "preferredAspect": {
          "type": "string",
          "enum": [
            "16:9",
            "4:3",
            "custom"
          ]
        },
        "editablePreference": {
          "type": "string",
          "enum": [
            "preferred",
            "not-required",
            "raster-ok"
          ]
        },
        "accessibilityTitle": {
          "type": "string",
          "minLength": 0,
          "maxLength": 512,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "includeNotes": {
          "type": "boolean"
        },
        "capabilityRequirements": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "mixed-direction",
              "custom-fonts",
              "charts",
              "tables",
              "transparency",
              "speaker-notes"
            ]
          },
          "minItems": 0,
          "maxItems": 16
        },
        "rendererFallback": {
          "type": "string",
          "enum": [
            "legacy",
            "raster",
            "fail"
          ]
        }
      },
      "required": [
        "preferredAspect",
        "includeNotes",
        "rendererFallback"
      ]
    },
    "documentCompatibility": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "sourceVersion": {
          "type": "string",
          "enum": [
            "canonical-v1",
            "v1-standard",
            "v2-standard",
            "template-v2"
          ]
        },
        "legacyPresentationVersion": {
          "type": "string",
          "minLength": 0,
          "maxLength": 64,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "legacyLayoutRef": {
          "type": "string",
          "minLength": 0,
          "maxLength": 128,
          "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
        },
        "requiresLegacyRenderer": {
          "type": "boolean"
        },
        "warnings": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/stableReference"
          },
          "minItems": 0,
          "maxItems": 256
        },
        "unsupportedFeatures": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/stableReference"
          },
          "minItems": 0,
          "maxItems": 256
        }
      },
      "required": [
        "sourceVersion",
        "requiresLegacyRenderer",
        "warnings",
        "unsupportedFeatures"
      ]
    },
    "extension": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "namespace": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9.-]{2,127}$"
        },
        "version": {
          "type": "string",
          "pattern": "^[0-9]+\\.[0-9]+$"
        },
        "value": {
          "oneOf": [
            {
              "type": "string",
              "minLength": 0,
              "maxLength": 2048,
              "pattern": "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$"
            },
            {
              "type": "number",
              "minimum": -1e12,
              "maximum": 1e12
            },
            {
              "type": "boolean"
            }
          ]
        }
      },
      "required": [
        "namespace",
        "version",
        "value"
      ]
    }
  }
};

// lib/presentation-document/validate.ts
var CANONICAL_LIMITS = Object.freeze({
  maxDocumentBytes: 5 * 1024 * 1024,
  maxTotalElements: 5e3,
  maxGroupDepth: 8,
  maxTotalTextCharacters: 2e6,
  maxNotesCharacters: 5e4,
  maxChartPoints: 5e3
});
var UNSAFE_TEXT = /<\s*\/?[a-z][^>]*>|javascript\s*:|data\s*:[^\s]+|on[a-z]+\s*=/i;
var ABSOLUTE_LOCAL_PATH = /(?:^|[\s"'])(?:[a-z]:[\\/]|file:\/\/|\/(?:home|users|tmp|var|etc|opt)\/)/i;
var UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
var PROTOTYPE_KEYS = /* @__PURE__ */ new Set(["__proto__", "constructor", "prototype"]);
function isObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function schemaObject(value) {
  return isObject(value) ? value : null;
}
function numberKeyword(schema, key) {
  const value = schema[key];
  return typeof value === "number" ? value : void 0;
}
function resolveRef(reference) {
  const name = reference.startsWith("#/$defs/") ? reference.slice(8) : "";
  const definitions = schemaObject(PRESENTATION_DOCUMENT_SCHEMA.$defs);
  return definitions ? schemaObject(definitions[name]) : null;
}
function validateSchema(value, schema, path, issues) {
  if (typeof schema.$ref === "string") {
    const target = resolveRef(schema.$ref);
    if (!target) issues.push({ code: "CANONICAL_SCHEMA_REFERENCE_INVALID", path });
    else validateSchema(value, target, path, issues);
    return;
  }
  if (Object.hasOwn(schema, "const") && value !== schema.const) {
    issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
    return;
  }
  if (Array.isArray(schema.enum) && !schema.enum.includes(value)) {
    issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
    return;
  }
  for (const keyword of ["oneOf", "anyOf"]) {
    const alternatives = schema[keyword];
    if (Array.isArray(alternatives)) {
      const matches = alternatives.filter((candidate) => {
        const candidateIssues = [];
        const node = schemaObject(candidate);
        if (node) validateSchema(value, node, path, candidateIssues);
        else candidateIssues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
        return candidateIssues.length === 0;
      }).length;
      if (keyword === "oneOf" && matches !== 1 || keyword === "anyOf" && matches === 0) {
        issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      }
      return;
    }
  }
  if (schema.type === "null") {
    if (value !== null) issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
    return;
  }
  if (schema.type === "boolean") {
    if (typeof value !== "boolean") issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
    return;
  }
  if (schema.type === "number" || schema.type === "integer") {
    if (typeof value !== "number" || !Number.isFinite(value) || schema.type === "integer" && !Number.isInteger(value)) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    const minimum = numberKeyword(schema, "minimum");
    const maximum = numberKeyword(schema, "maximum");
    const exclusiveMinimum = numberKeyword(schema, "exclusiveMinimum");
    const multipleOf = numberKeyword(schema, "multipleOf");
    if (minimum !== void 0 && value < minimum || maximum !== void 0 && value > maximum || exclusiveMinimum !== void 0 && value <= exclusiveMinimum || multipleOf !== void 0 && Math.abs(value / multipleOf - Math.round(value / multipleOf)) > 1e-9) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
    }
    return;
  }
  if (schema.type === "string") {
    if (typeof value !== "string") {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    const minLength = numberKeyword(schema, "minLength");
    const maxLength = numberKeyword(schema, "maxLength");
    if (minLength !== void 0 && value.length < minLength || maxLength !== void 0 && value.length > maxLength || typeof schema.pattern === "string" && !new RegExp(schema.pattern, "u").test(value) || schema.format === "uuid" && !UUID.test(value)) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    if (schema.format === "uri") {
      try {
        new URL(value);
      } catch {
        issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      }
    }
    return;
  }
  if (schema.type === "array") {
    if (!Array.isArray(value)) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    const minItems = numberKeyword(schema, "minItems");
    const maxItems = numberKeyword(schema, "maxItems");
    if (minItems !== void 0 && value.length < minItems || maxItems !== void 0 && value.length > maxItems) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    const itemSchema = schemaObject(schema.items);
    if (itemSchema) value.forEach((item, index) => validateSchema(item, itemSchema, `${path}[${index}]`, issues));
    return;
  }
  if (schema.type === "object") {
    if (!isObject(value)) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    const properties = schemaObject(schema.properties) ?? {};
    const required = Array.isArray(schema.required) ? new Set(schema.required.filter((name) => typeof name === "string")) : /* @__PURE__ */ new Set();
    for (const name of required) {
      if (!Object.hasOwn(value, name)) issues.push({ code: "CANONICAL_SCHEMA_INVALID", path: `${path}.${name}` });
    }
    for (const [name, child] of Object.entries(value)) {
      const childSchema = schemaObject(properties[name]);
      if (!childSchema) {
        if (schema.additionalProperties === false) issues.push({ code: "CANONICAL_UNKNOWN_FIELD", path: `${path}.${name}` });
      } else {
        validateSchema(child, childSchema, `${path}.${name}`, issues);
      }
    }
  }
}
function rawSafetyScan(value) {
  let serialized;
  try {
    serialized = JSON.stringify(value);
  } catch {
    return { code: "CANONICAL_JSON_INVALID", path: "$" };
  }
  if (serialized === void 0 || new TextEncoder().encode(serialized).byteLength > CANONICAL_LIMITS.maxDocumentBytes) {
    return { code: "CANONICAL_DOCUMENT_TOO_LARGE", path: "$" };
  }
  const stack = [{ value, depth: 0, path: "$" }];
  while (stack.length) {
    const current = stack.pop();
    if (!current) break;
    if (current.depth > 32) return { code: "CANONICAL_NESTING_EXCESSIVE", path: current.path };
    if (typeof current.value === "string" && UNSAFE_TEXT.test(current.value)) {
      return { code: "CANONICAL_EXECUTABLE_CONTENT", path: current.path };
    }
    if (typeof current.value === "string" && ABSOLUTE_LOCAL_PATH.test(current.value)) {
      return { code: "CANONICAL_LOCAL_PATH_FORBIDDEN", path: current.path };
    }
    if (typeof current.value === "number" && !Number.isFinite(current.value)) {
      return { code: "CANONICAL_NONFINITE_NUMBER", path: current.path };
    }
    if (Array.isArray(current.value)) {
      current.value.forEach((child, index) => stack.push({ value: child, depth: current.depth + 1, path: `${current.path}[${index}]` }));
    } else if (isObject(current.value)) {
      for (const [key, child] of Object.entries(current.value)) {
        if (PROTOTYPE_KEYS.has(key)) return { code: "CANONICAL_PROTOTYPE_KEY", path: `${current.path}.${key}` };
        stack.push({ value: child, depth: current.depth + 1, path: `${current.path}.${key}` });
      }
    }
  }
  return null;
}
function isSafeExternalUrl(value) {
  try {
    const parsed = new URL(value);
    const host = parsed.hostname.replace(/\.$/, "").replace(/^\[|\]$/g, "").toLowerCase();
    if (parsed.protocol !== "https:" || parsed.username || parsed.password || host === "localhost" || host.endsWith(".local")) return false;
    const ipv4 = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/)?.slice(1).map(Number);
    if (ipv4 && ipv4.every((part) => part <= 255)) {
      const [first, second] = ipv4;
      if (first === 0 || first === 10 || first === 127 || first >= 224 || first === 100 && second >= 64 && second <= 127 || first === 169 && second === 254 || first === 172 && second >= 16 && second <= 31 || first === 192 && (second === 0 || second === 168) || first === 198 && (second === 18 || second === 19 || second === 51) || first === 203 && second === 0) return false;
    }
    if (host === "::" || host === "::1" || host.startsWith("fc") || host.startsWith("fd") || host.startsWith("::ffff:") || /^fe[89ab]/.test(host) || host.startsWith("ff")) return false;
    return true;
  } catch {
    return false;
  }
}
function semanticValidation(document) {
  const seen = /* @__PURE__ */ new Set();
  const addId = (id, path) => {
    if (seen.has(id)) return { code: "CANONICAL_DUPLICATE_ID", path };
    seen.add(id);
    return null;
  };
  let issue = addId(document.documentId, "$.documentId");
  if (issue) return issue;
  const assets = /* @__PURE__ */ new Set();
  for (let index = 0; index < document.assets.length; index += 1) {
    const id = document.assets[index].assetId;
    issue = addId(id, `$.assets[${index}].assetId`);
    if (issue) return issue;
    assets.add(id);
  }
  const fontIds = new Set(document.fontPolicy.families.map((family) => family.id));
  if (fontIds.size !== document.fontPolicy.families.length) return { code: "CANONICAL_DUPLICATE_FONT_REFERENCE", path: "$.fontPolicy.families" };
  if (document.fontPolicy.defaultBodyRef && !fontIds.has(document.fontPolicy.defaultBodyRef)) return { code: "CANONICAL_FONT_REFERENCE_INVALID", path: "$.fontPolicy.defaultBodyRef" };
  if (document.fontPolicy.defaultHeadingRef && !fontIds.has(document.fontPolicy.defaultHeadingRef)) return { code: "CANONICAL_FONT_REFERENCE_INVALID", path: "$.fontPolicy.defaultHeadingRef" };
  if (document.fontPolicy.families.some((family) => family.assetId && !assets.has(family.assetId))) return { code: "CANONICAL_ASSET_REFERENCE_INVALID", path: "$.fontPolicy.families.assetId" };
  const validateTextRun = (run, path) => {
    if (run.fontFamilyRef && !fontIds.has(run.fontFamilyRef)) return { code: "CANONICAL_FONT_REFERENCE_INVALID", path: `${path}.fontFamilyRef` };
    if (run.hyperlink?.kind === "external" && (!run.hyperlink.href || run.hyperlink.assetId || !isSafeExternalUrl(run.hyperlink.href))) return { code: "CANONICAL_URL_UNSAFE", path: `${path}.hyperlink` };
    if (run.hyperlink?.kind === "asset" && (!run.hyperlink.assetId || run.hyperlink.href || !assets.has(run.hyperlink.assetId))) return { code: "CANONICAL_ASSET_REFERENCE_INVALID", path: `${path}.hyperlink` };
    return null;
  };
  const orders = /* @__PURE__ */ new Set();
  let totalElements = 0;
  let totalText = document.title.length;
  for (let slideIndex = 0; slideIndex < document.slides.length; slideIndex += 1) {
    const slide = document.slides[slideIndex];
    issue = addId(slide.id, `$.slides[${slideIndex}].id`);
    if (issue) return issue;
    if (orders.has(slide.order)) return { code: "CANONICAL_DUPLICATE_SLIDE_ORDER", path: `$.slides[${slideIndex}].order` };
    orders.add(slide.order);
    if (slide.background?.assetId && !assets.has(slide.background.assetId)) return { code: "CANONICAL_ASSET_REFERENCE_INVALID", path: `$.slides[${slideIndex}].background.assetId` };
    if (slide.speakerNotes) {
      issue = addId(slide.speakerNotes.id, `$.slides[${slideIndex}].speakerNotes.id`);
      if (issue) return issue;
      let noteCharacters = 0;
      for (const paragraph of slide.speakerNotes.paragraphs) {
        issue = addId(paragraph.id, `$.slides[${slideIndex}].speakerNotes.paragraphs`);
        if (issue) return issue;
        for (const run of paragraph.runs) {
          issue = addId(run.id, `$.slides[${slideIndex}].speakerNotes.paragraphs.runs`);
          if (issue) return issue;
          noteCharacters += run.text.length;
          issue = validateTextRun(run, `$.slides[${slideIndex}].speakerNotes.paragraphs.runs`);
          if (issue) return issue;
        }
      }
      if (noteCharacters > CANONICAL_LIMITS.maxNotesCharacters) return { code: "CANONICAL_NOTES_TOO_LARGE", path: `$.slides[${slideIndex}].speakerNotes` };
    }
    const stack = slide.elements.map((element) => ({ element, depth: 1 }));
    while (stack.length) {
      const current = stack.pop();
      if (!current) break;
      totalElements += 1;
      if (current.depth > CANONICAL_LIMITS.maxGroupDepth) return { code: "CANONICAL_GROUP_DEPTH_EXCEEDED", path: `$.slides[${slideIndex}].elements` };
      issue = addId(current.element.id, `$.slides[${slideIndex}].elements`);
      if (issue) return issue;
      if (current.element.type === "image" && !assets.has(current.element.assetId)) return { code: "CANONICAL_ASSET_REFERENCE_INVALID", path: `$.slides[${slideIndex}].elements` };
      if (current.element.type === "icon" && !current.element.assetId && !current.element.iconName) return { code: "CANONICAL_ICON_REFERENCE_REQUIRED", path: `$.slides[${slideIndex}].elements` };
      if (current.element.type === "icon" && current.element.assetId && !assets.has(current.element.assetId)) return { code: "CANONICAL_ASSET_REFERENCE_INVALID", path: `$.slides[${slideIndex}].elements` };
      if (current.element.type === "text") {
        for (const paragraph of current.element.paragraphs) {
          issue = addId(paragraph.id, `$.slides[${slideIndex}].elements.paragraphs`);
          if (issue) return issue;
          for (const run of paragraph.runs) {
            issue = addId(run.id, `$.slides[${slideIndex}].elements.paragraphs.runs`);
            if (issue) return issue;
            totalText += run.text.length;
            issue = validateTextRun(run, `$.slides[${slideIndex}].elements.paragraphs.runs`);
            if (issue) return issue;
          }
        }
      }
      if (current.element.type === "table") {
        const width = current.element.rows[0]?.cells.length ?? 0;
        if (current.element.rows.some((row) => row.cells.length !== width)) return { code: "CANONICAL_TABLE_SHAPE_INVALID", path: `$.slides[${slideIndex}].elements.rows` };
        for (const row of current.element.rows) for (const cell of row.cells) for (const paragraph of cell.paragraphs) {
          issue = addId(paragraph.id, `$.slides[${slideIndex}].elements.rows.cells.paragraphs`);
          if (issue) return issue;
          for (const run of paragraph.runs) {
            issue = addId(run.id, `$.slides[${slideIndex}].elements.rows.cells.paragraphs.runs`);
            if (issue) return issue;
            totalText += run.text.length;
            issue = validateTextRun(run, `$.slides[${slideIndex}].elements.rows.cells.paragraphs.runs`);
            if (issue) return issue;
          }
        }
      }
      if (current.element.type === "chart") {
        issue = addId(current.element.chartId, `$.slides[${slideIndex}].elements.chartId`);
        if (issue) return issue;
        let points = 0;
        for (const series of current.element.series) {
          issue = addId(series.id, `$.slides[${slideIndex}].elements.series.id`);
          if (issue) return issue;
          points += series.values.length;
        }
        if (points > CANONICAL_LIMITS.maxChartPoints) return { code: "CANONICAL_CHART_TOO_LARGE", path: `$.slides[${slideIndex}].elements.series` };
      }
      if (current.element.type === "container" || current.element.type === "group") {
        current.element.children.forEach((element) => stack.push({ element, depth: current.depth + 1 }));
      }
    }
  }
  if (totalElements > CANONICAL_LIMITS.maxTotalElements) return { code: "CANONICAL_ELEMENTS_EXCESSIVE", path: "$.slides" };
  if (totalText > CANONICAL_LIMITS.maxTotalTextCharacters) return { code: "CANONICAL_TEXT_EXCESSIVE", path: "$.slides" };
  if (orders.size !== document.slides.length || [...orders].some((order) => order < 0 || order >= document.slides.length)) return { code: "CANONICAL_SLIDE_ORDER_INVALID", path: "$.slides" };
  return null;
}
function validatePresentationDocument(input) {
  const safetyIssue = rawSafetyScan(input);
  if (safetyIssue) return { ok: false, issues: [safetyIssue] };
  const normalizedInput = normalizedValue(input);
  const issues = [];
  validateSchema(normalizedInput, PRESENTATION_DOCUMENT_SCHEMA, "$", issues);
  if (issues.length) return { ok: false, issues: issues.slice(0, 50) };
  const document = normalizedInput;
  const semanticIssue = semanticValidation(document);
  return semanticIssue ? { ok: false, issues: [semanticIssue] } : { ok: true, document };
}
function normalizedValue(value) {
  if (Array.isArray(value)) return value.map(normalizedValue);
  if (isObject(value)) {
    const sorted = {};
    for (const key of Object.keys(value).sort()) {
      if (value[key] !== null) sorted[key] = normalizedValue(value[key]);
    }
    return sorted;
  }
  return value;
}
function canonicalJson(document) {
  return JSON.stringify(normalizedValue(document));
}
async function canonicalChecksum(document) {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalJson(document)));
  return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
}

// components/editor/commands/document-index.ts
function elementChildren(element) {
  return element.type === "group" || element.type === "container" ? element.children : [];
}
function indexDocumentElements(document) {
  const index = /* @__PURE__ */ new Map();
  for (const slide of document.slides) {
    walkElements(slide.elements, slide.id, null, 0, index);
  }
  return index;
}
function walkElements(elements, slideId, parentId, depth, index) {
  elements.forEach((element, elementIndex) => {
    index.set(element.id, {
      slideId,
      element,
      parentId,
      depth,
      index: elementIndex
    });
    const children = elementChildren(element);
    if (children.length) walkElements(children, slideId, element.id, depth + 1, index);
  });
}
function countDocumentElements(document) {
  return indexDocumentElements(document).size;
}
function updateElementTree(elements, targetIds, updater) {
  let changed = false;
  const next = elements.map((element) => {
    let candidate = targetIds.has(element.id) ? updater(element) : element;
    if (candidate.type === "group" || candidate.type === "container") {
      const children = updateElementTree(candidate.children, targetIds, updater);
      if (children !== candidate.children) candidate = { ...candidate, children };
    }
    if (candidate !== element) changed = true;
    return candidate;
  });
  return changed ? next : elements;
}
function removeElementsFromTree(elements, targetIds) {
  let changed = false;
  const next = [];
  for (const element of elements) {
    if (targetIds.has(element.id)) {
      changed = true;
      continue;
    }
    let candidate = element;
    if (element.type === "group" || element.type === "container") {
      const children = removeElementsFromTree(element.children, targetIds);
      if (children !== element.children) candidate = { ...element, children };
    }
    if (candidate !== element) changed = true;
    next.push(candidate);
  }
  return changed ? next : elements;
}
function replaceElementInTree(elements, targetId, replacement) {
  let changed = false;
  const next = [];
  for (const element of elements) {
    if (element.id === targetId) {
      next.push(...replacement);
      changed = true;
      continue;
    }
    let candidate = element;
    if (element.type === "group" || element.type === "container") {
      const children = replaceElementInTree(element.children, targetId, replacement);
      if (children !== element.children) candidate = { ...element, children };
    }
    if (candidate !== element) changed = true;
    next.push(candidate);
  }
  return changed ? next : elements;
}
function insertElementInTree(elements, element, parentId) {
  if (!parentId) return [...elements, element];
  return updateElementTree(elements, /* @__PURE__ */ new Set([parentId]), (parent) => {
    if (parent.type !== "group" && parent.type !== "container") return parent;
    return { ...parent, children: [...parent.children, element] };
  });
}
function updateSlide(document, slideId, updater) {
  let changed = false;
  const slides = document.slides.map((slide) => {
    if (slide.id !== slideId) return slide;
    changed = true;
    return updater(slide);
  });
  return changed ? { ...document, slides } : document;
}
function normalizeElementOrder(elements) {
  const sorted = [...elements].sort((a, b) => a.zOrder - b.zOrder || a.id.localeCompare(b.id));
  return sorted.map((element, index) => {
    let candidate = element.zOrder === index ? element : { ...element, zOrder: index };
    if (candidate.type === "group" || candidate.type === "container") {
      const previousChildren = candidate.children;
      const children = normalizeElementOrder(previousChildren);
      if (children.some((child, childIndex) => child !== previousChildren[childIndex])) {
        candidate = { ...candidate, children };
      }
    }
    return candidate;
  });
}
function normalizeSlideOrder(slides) {
  return slides.map((slide, order) => slide.order === order ? slide : { ...slide, order });
}
function rotatedBoundingBox(geometry, rotation = 0) {
  const radians = rotation * Math.PI / 180;
  const cosine = Math.abs(Math.cos(radians));
  const sine = Math.abs(Math.sin(radians));
  const width = geometry.width * cosine + geometry.height * sine;
  const height = geometry.width * sine + geometry.height * cosine;
  const centerX = geometry.x + geometry.width / 2;
  const centerY = geometry.y + geometry.height / 2;
  return {
    left: centerX - width / 2,
    top: centerY - height / 2,
    right: centerX + width / 2,
    bottom: centerY + height / 2
  };
}
function unionBoundingBoxes(boxes) {
  return {
    left: Math.min(...boxes.map((box) => box.left)),
    top: Math.min(...boxes.map((box) => box.top)),
    right: Math.max(...boxes.map((box) => box.right)),
    bottom: Math.max(...boxes.map((box) => box.bottom))
  };
}

// components/editor/commands/validate.ts
var COMMAND_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
var LOCK_BYPASS_TYPES = /* @__PURE__ */ new Set([
  "LOCK_ELEMENTS",
  "UNLOCK_ELEMENTS",
  "HIDE_ELEMENTS",
  "SHOW_ELEMENTS"
]);
function validateCommand(document, command, options = {}) {
  const issues = [];
  const baseValidation = options.assumeValidDocument ? null : validatePresentationDocument(document);
  if (baseValidation && !baseValidation.ok) {
    return {
      ok: false,
      issues: [{ code: "EDITOR_DOCUMENT_INVALID", detail: baseValidation.issues[0]?.code }]
    };
  }
  if (!COMMAND_ID.test(command.commandId)) issues.push({ code: "EDITOR_COMMAND_ID_INVALID" });
  if (new Set(command.targetIds).size !== command.targetIds.length) {
    issues.push({ code: "EDITOR_COMMAND_DUPLICATE_TARGET" });
  }
  if (!isSerializable(command)) issues.push({ code: "EDITOR_COMMAND_NOT_SERIALIZABLE" });
  if (command.type === "BATCH") {
    if (command.payload.commands.length === 0) issues.push({ code: "EDITOR_COMMAND_BATCH_EMPTY" });
    const nestedIds = /* @__PURE__ */ new Set();
    for (const nested of command.payload.commands) {
      if (nestedIds.has(nested.commandId)) issues.push({ code: "EDITOR_COMMAND_ID_DUPLICATE", detail: nested.commandId });
      nestedIds.add(nested.commandId);
    }
    return issues.length ? { ok: false, issues } : { ok: true };
  }
  const slides = new Map(document.slides.map((slide) => [slide.id, slide]));
  const elementIndex = indexDocumentElements(document);
  const targetPaths = command.targetIds.flatMap((targetId) => {
    const path = elementIndex.get(targetId);
    return path ? [path] : [];
  });
  const slideId = "slideId" in command.payload ? command.payload.slideId : null;
  if (slideId && !slides.has(slideId)) issues.push({ code: "EDITOR_SLIDE_NOT_FOUND", targetId: slideId });
  const newElementIds = command.type === "ADD_ELEMENT" ? [command.payload.element.id] : command.type === "DUPLICATE_ELEMENTS" ? command.payload.copies.flatMap((copy) => collectElementIds(copy.element)) : [];
  if (newElementIds.length) {
    if (new Set(newElementIds).size !== newElementIds.length) issues.push({ code: "EDITOR_DUPLICATE_ID" });
    for (const id of newElementIds) {
      if (elementIndex.has(id)) issues.push({ code: "EDITOR_DUPLICATE_ID", targetId: id });
    }
    if (countDocumentElements(document) + newElementIds.length > CANONICAL_LIMITS.maxTotalElements) {
      issues.push({ code: "EDITOR_ELEMENT_LIMIT_EXCEEDED" });
    }
  }
  const elementTargetCommand = ![
    "ADD_ELEMENT",
    "ADD_SLIDE",
    "DELETE_SLIDE",
    "DUPLICATE_SLIDE",
    "REORDER_SLIDES",
    "UPDATE_SLIDE"
  ].includes(command.type);
  if (elementTargetCommand) {
    for (const targetId of command.targetIds) {
      const path = elementIndex.get(targetId);
      if (!path) issues.push({ code: "EDITOR_ELEMENT_NOT_FOUND", targetId });
      else if (slideId && path.slideId !== slideId) issues.push({ code: "EDITOR_TARGET_SLIDE_MISMATCH", targetId });
    }
  }
  if (!LOCK_BYPASS_TYPES.has(command.type)) {
    for (const path of targetPaths) {
      const lockedId = firstLockedId(path.element);
      if (lockedId) issues.push({ code: "EDITOR_ELEMENT_LOCKED", targetId: lockedId });
    }
  }
  if (command.type === "ADD_ELEMENT" && command.targetIds[0] !== command.payload.element.id) {
    issues.push({ code: "EDITOR_COMMAND_TARGET_MISMATCH" });
  }
  if (command.type === "ADD_ELEMENT" && command.payload.parentId) {
    validateParent(command.payload.parentId, command.payload.slideId, elementIndex, issues);
  }
  if (command.type === "DUPLICATE_ELEMENTS") {
    if (command.payload.copies.length !== command.targetIds.length || command.payload.copies.some((copy) => !command.targetIds.includes(copy.sourceId))) {
      issues.push({ code: "EDITOR_COMMAND_TARGET_MISMATCH" });
    }
    for (const copy of command.payload.copies) {
      const source = elementIndex.get(copy.sourceId);
      if (!source) issues.push({ code: "EDITOR_ELEMENT_NOT_FOUND", targetId: copy.sourceId });
      if (copy.parentId) validateParent(copy.parentId, command.payload.slideId, elementIndex, issues);
    }
  }
  if (["GROUP_ELEMENTS", "ALIGN_ELEMENTS", "DISTRIBUTE_ELEMENTS"].includes(command.type)) {
    const parents = new Set(targetPaths.map((path) => path.parentId));
    if (parents.size > 1) issues.push({ code: "EDITOR_TARGET_PARENT_MISMATCH" });
  }
  if (command.type === "GROUP_ELEMENTS") {
    if (command.targetIds.length < 2) issues.push({ code: "EDITOR_GROUP_REQUIRES_MULTIPLE" });
    if (elementIndex.has(command.payload.group.id)) issues.push({ code: "EDITOR_DUPLICATE_ID", targetId: command.payload.group.id });
    if (command.payload.group.children.length) issues.push({ code: "EDITOR_GROUP_PAYLOAD_CHILDREN_FORBIDDEN" });
    if (command.payload.parentId) validateParent(command.payload.parentId, command.payload.slideId, elementIndex, issues);
    const targetParent = targetPaths[0]?.parentId ?? void 0;
    if (targetParent !== command.payload.parentId) issues.push({ code: "EDITOR_TARGET_PARENT_MISMATCH" });
  }
  if (command.type === "UNGROUP_ELEMENTS") {
    targetPaths.filter((path) => path.element.type !== "group").forEach((path) => {
      issues.push({ code: "EDITOR_UNGROUP_TARGET_INVALID", targetId: path.element.id });
    });
  }
  if (command.type === "ALIGN_ELEMENTS" && command.targetIds.length < 2) {
    issues.push({ code: "EDITOR_ALIGNMENT_REQUIRES_MULTIPLE" });
  }
  if (command.type === "DISTRIBUTE_ELEMENTS" && command.targetIds.length < 3) {
    issues.push({ code: "EDITOR_DISTRIBUTION_REQUIRES_THREE" });
  }
  if (command.type === "UPDATE_TEXT") {
    targetPaths.filter((path) => path.element.type !== "text").forEach((path) => {
      issues.push({ code: "EDITOR_TEXT_TARGET_INVALID", targetId: path.element.id });
    });
  }
  if (command.type === "REPLACE_ASSET") {
    if (!document.assets.some((asset) => asset.assetId === command.payload.assetId)) {
      issues.push({ code: "EDITOR_ASSET_NOT_FOUND", targetId: command.payload.assetId });
    }
    targetPaths.filter((path) => path.element.type !== "image" && path.element.type !== "icon").forEach((path) => {
      issues.push({ code: "EDITOR_ASSET_TARGET_INVALID", targetId: path.element.id });
    });
  }
  if (command.type === "DELETE_SLIDE" || command.type === "UPDATE_SLIDE") {
    command.targetIds.filter((id) => !slides.has(id)).forEach((id) => {
      issues.push({ code: "EDITOR_SLIDE_NOT_FOUND", targetId: id });
    });
  }
  if (command.type === "ADD_SLIDE" && slides.has(command.payload.slide.id)) {
    issues.push({ code: "EDITOR_DUPLICATE_ID", targetId: command.payload.slide.id });
  }
  if (command.type === "DUPLICATE_SLIDE") {
    for (const copy of command.payload.copies) {
      if (!slides.has(copy.sourceId)) issues.push({ code: "EDITOR_SLIDE_NOT_FOUND", targetId: copy.sourceId });
      if (slides.has(copy.slide.id)) issues.push({ code: "EDITOR_DUPLICATE_ID", targetId: copy.slide.id });
    }
  }
  if (command.type === "REORDER_SLIDES") {
    const currentIds = new Set(slides.keys());
    const ordered = command.payload.orderedSlideIds;
    if (ordered.length !== currentIds.size || new Set(ordered).size !== ordered.length || ordered.some((id) => !currentIds.has(id))) {
      issues.push({ code: "EDITOR_SLIDE_ORDER_INVALID" });
    }
  }
  if (command.type === "REORDER_ELEMENTS") {
    if (command.payload.parentId) validateParent(command.payload.parentId, command.payload.slideId, elementIndex, issues);
    const slide = slides.get(command.payload.slideId);
    const siblings = slide ? siblingElements(slide.elements, command.payload.parentId) : null;
    const ordered = command.payload.orderedIds;
    if (!siblings || ordered.length !== siblings.length || new Set(ordered).size !== ordered.length || ordered.some((id) => !siblings.some((element) => element.id === id))) {
      issues.push({ code: "EDITOR_ELEMENT_ORDER_INVALID" });
    } else {
      const previous = [...siblings].sort((a, b) => a.zOrder - b.zOrder || a.id.localeCompare(b.id));
      previous.forEach((element, index) => {
        if (element.locked && ordered.indexOf(element.id) !== index) issues.push({ code: "EDITOR_ELEMENT_LOCKED", targetId: element.id });
      });
    }
  }
  if (!allFinite(command.payload)) issues.push({ code: "EDITOR_NONFINITE_NUMBER" });
  return issues.length ? { ok: false, issues } : { ok: true };
}
function firstLockedId(element) {
  if (element.locked) return element.id;
  if (element.type === "group" || element.type === "container") {
    for (const child of element.children) {
      const locked = firstLockedId(child);
      if (locked) return locked;
    }
  }
  return null;
}
function siblingElements(elements, parentId) {
  if (!parentId) return elements;
  for (const element of elements) {
    if (element.id === parentId && (element.type === "group" || element.type === "container")) return element.children;
    if (element.type === "group" || element.type === "container") {
      const nested = siblingElements(element.children, parentId);
      if (nested) return nested;
    }
  }
  return null;
}
function validateParent(parentId, slideId, index, issues) {
  const parent = index.get(parentId);
  if (!parent) issues.push({ code: "EDITOR_PARENT_NOT_FOUND", targetId: parentId });
  else if (parent.slideId !== slideId) issues.push({ code: "EDITOR_TARGET_SLIDE_MISMATCH", targetId: parentId });
  else if (parent.element.type !== "group" && parent.element.type !== "container") {
    issues.push({ code: "EDITOR_PARENT_TYPE_INVALID", targetId: parentId });
  }
}
function collectElementIds(element) {
  return [
    element.id,
    ...element.type === "group" || element.type === "container" ? element.children.flatMap(collectElementIds) : []
  ];
}
function isSerializable(value) {
  const stack = [value];
  const seen = /* @__PURE__ */ new Set();
  while (stack.length) {
    const current = stack.pop();
    if (typeof current === "function" || typeof current === "symbol" || typeof current === "bigint" || current === void 0) return false;
    if (!current || typeof current !== "object") continue;
    if (seen.has(current)) continue;
    seen.add(current);
    if (Array.isArray(current)) stack.push(...current);
    else stack.push(...Object.values(current));
  }
  try {
    const serialized = JSON.stringify(value);
    return serialized !== void 0 && JSON.parse(serialized) != null;
  } catch {
    return false;
  }
}
function allFinite(value) {
  const stack = [value];
  while (stack.length) {
    const current = stack.pop();
    if (typeof current === "number" && !Number.isFinite(current)) return false;
    if (Array.isArray(current)) stack.push(...current);
    else if (current && typeof current === "object") stack.push(...Object.values(current));
  }
  return true;
}

// components/editor/commands/apply.ts
var EditorCommandError = class extends Error {
  constructor(code, targetId, detail) {
    super(detail ? `${code}:${detail}` : code);
    this.code = code;
    this.targetId = targetId;
    this.name = "EditorCommandError";
  }
};
function applyCommand(document, command) {
  if (command.type === "RESTORE_DOCUMENT") {
    return assertValidResult(command.payload.document);
  }
  if (command.type === "BATCH") {
    assertCommandIsValid(document, command, false);
    return applyCommandBatch(document, command.payload.commands);
  }
  return applyEditorCommand(document, command, false);
}
function applyEditorCommand(document, command, assumeValidDocument) {
  assertCommandIsValid(document, command, assumeValidDocument);
  return assertValidResult(applyValidatedCommand(document, command));
}
function assertCommandIsValid(document, command, assumeValidDocument) {
  const validation = validateCommand(document, command, { assumeValidDocument });
  if (!validation.ok) {
    const issue = validation.issues[0];
    throw new EditorCommandError(issue?.code ?? "EDITOR_COMMAND_INVALID", issue?.targetId, issue?.detail);
  }
}
function applyCommandBatch(document, commands) {
  let next = document;
  for (const command of commands) next = applyCommand(next, command);
  return next;
}
function applyValidatedCommand(document, command) {
  switch (command.type) {
    case "ADD_ELEMENT":
      return updateElementsOnSlide(document, command.payload.slideId, (elements) => insertElementInTree(elements, command.payload.element, command.payload.parentId));
    case "DELETE_ELEMENTS":
      return updateElementsOnSlide(document, command.payload.slideId, (elements) => removeElementsFromTree(elements, new Set(command.targetIds)));
    case "DUPLICATE_ELEMENTS":
      return updateElementsOnSlide(document, command.payload.slideId, (elements) => command.payload.copies.reduce(
        (current, copy) => insertElementInTree(current, copy.element, copy.parentId),
        elements
      ));
    case "UPDATE_ELEMENT":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({
        ...element,
        ...command.payload.changes
      }));
    case "MOVE_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({
        ...element,
        geometry: {
          ...element.geometry,
          x: element.geometry.x + command.payload.deltaX,
          y: element.geometry.y + command.payload.deltaY
        }
      }));
    case "RESIZE_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({
        ...element,
        geometry: command.payload.geometryById[element.id] ?? element.geometry
      }));
    case "ROTATE_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({
        ...element,
        transform: {
          ...element.transform ?? {},
          rotation: command.payload.rotationById[element.id] ?? element.transform?.rotation ?? 0
        }
      }));
    case "REORDER_ELEMENTS":
      return reorderElements(document, command.payload.slideId, command.payload.orderedIds, command.payload.parentId);
    case "GROUP_ELEMENTS":
      return groupElements(document, command.payload.slideId, command.targetIds, command.payload.group, command.payload.parentId);
    case "UNGROUP_ELEMENTS":
      return ungroupElements(document, command.payload.slideId, command.targetIds);
    case "LOCK_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({ ...element, locked: true }));
    case "UNLOCK_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({ ...element, locked: false }));
    case "HIDE_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({ ...element, hidden: true }));
    case "SHOW_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({ ...element, hidden: false }));
    case "ALIGN_ELEMENTS":
      return alignElements(document, command.payload.slideId, command.targetIds, command.payload.alignment);
    case "DISTRIBUTE_ELEMENTS":
      return distributeElements(document, command.payload.slideId, command.targetIds, command.payload.axis);
    case "UPDATE_TEXT":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => element.type === "text" ? { ...element, paragraphs: command.payload.paragraphs } : element);
    case "UPDATE_STYLE":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({
        ...element,
        style: { ...element.style ?? {}, ...command.payload.style }
      }));
    case "REPLACE_ASSET":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => {
        if (element.type === "image" || element.type === "icon") return { ...element, assetId: command.payload.assetId };
        return element;
      });
    case "ADD_SLIDE":
      return { ...document, slides: normalizeSlideOrder([...document.slides, command.payload.slide]) };
    case "DELETE_SLIDE":
      return { ...document, slides: normalizeSlideOrder(document.slides.filter((slide) => !command.targetIds.includes(slide.id))) };
    case "DUPLICATE_SLIDE":
      return { ...document, slides: normalizeSlideOrder([...document.slides, ...command.payload.copies.map((copy) => copy.slide)]) };
    case "REORDER_SLIDES": {
      const byId = new Map(document.slides.map((slide) => [slide.id, slide]));
      return { ...document, slides: command.payload.orderedSlideIds.map((id, order) => ({ ...byId.get(id), order })) };
    }
    case "UPDATE_SLIDE":
      return { ...document, slides: document.slides.map((slide) => command.targetIds.includes(slide.id) ? { ...slide, ...command.payload.changes } : slide) };
  }
}
function updateElementsOnSlide(document, slideId, updater) {
  return updateSlide(document, slideId, (slide) => ({
    ...slide,
    elements: normalizeElementOrder(updater(slide.elements))
  }));
}
function updateTargets(document, slideId, targetIds, updater) {
  const targets = new Set(targetIds);
  return updateElementsOnSlide(document, slideId, (elements) => updateElementTree(elements, targets, updater));
}
function updateParentChildren(slide, parentId, updater) {
  if (!parentId) return { ...slide, elements: normalizeElementOrder(updater(slide.elements)) };
  const elements = updateElementTree(slide.elements, /* @__PURE__ */ new Set([parentId]), (parent) => {
    if (parent.type !== "group" && parent.type !== "container") return parent;
    return { ...parent, children: normalizeElementOrder(updater(parent.children)) };
  });
  return { ...slide, elements: normalizeElementOrder(elements) };
}
function reorderElements(document, slideId, orderedIds, parentId) {
  return updateSlide(document, slideId, (slide) => updateParentChildren(slide, parentId, (children) => {
    const byId = new Map(children.map((element) => [element.id, element]));
    const ordered = orderedIds.flatMap((id) => byId.get(id) ? [byId.get(id)] : []);
    const remaining = children.filter((element) => !orderedIds.includes(element.id));
    return [...ordered, ...remaining];
  }));
}
function groupElements(document, slideId, targetIds, group, parentId) {
  const targets = new Set(targetIds);
  return updateSlide(document, slideId, (slide) => updateParentChildren(slide, parentId, (children) => {
    const selected = children.filter((element) => targets.has(element.id));
    const firstIndex = Math.min(...selected.map((element) => children.indexOf(element)));
    const relativeChildren = selected.map((element) => ({
      ...element,
      geometry: {
        ...element.geometry,
        x: element.geometry.x - group.geometry.x,
        y: element.geometry.y - group.geometry.y
      }
    }));
    const candidate = { ...group, children: normalizeElementOrder(relativeChildren) };
    const next = children.filter((element) => !targets.has(element.id));
    next.splice(firstIndex, 0, candidate);
    return next;
  }));
}
function ungroupElements(document, slideId, targetIds) {
  return updateSlide(document, slideId, (slide) => {
    let elements = slide.elements;
    for (const targetId of targetIds) {
      const path = indexSlide({ ...slide, elements }).get(targetId);
      if (!path || path.element.type !== "group") continue;
      const group = path.element;
      const rotation = group.transform?.rotation ?? 0;
      const children = group.children.map((child) => {
        const geometry = {
          ...child.geometry,
          x: child.geometry.x + group.geometry.x,
          y: child.geometry.y + group.geometry.y
        };
        return rotation ? { ...child, geometry, transform: { ...child.transform ?? {}, rotation: (child.transform?.rotation ?? 0) + rotation } } : { ...child, geometry };
      });
      elements = replaceElementInTree(elements, targetId, children);
    }
    return { ...slide, elements: normalizeElementOrder(elements) };
  });
}
function alignElements(document, slideId, targetIds, alignment) {
  const index = indexDocumentElements(document);
  const targets = targetIds.map((id) => index.get(id).element);
  const boxes = targets.map((element) => rotatedBoundingBox(element.geometry, element.transform?.rotation));
  const union = unionBoundingBoxes(boxes);
  const geometryById = /* @__PURE__ */ new Map();
  targets.forEach((element, i) => {
    const box = boxes[i];
    let dx = 0;
    let dy = 0;
    if (alignment === "start") dx = union.left - box.left;
    if (alignment === "center-horizontal") dx = (union.left + union.right - box.left - box.right) / 2;
    if (alignment === "end") dx = union.right - box.right;
    if (alignment === "top") dy = union.top - box.top;
    if (alignment === "center-vertical") dy = (union.top + union.bottom - box.top - box.bottom) / 2;
    if (alignment === "bottom") dy = union.bottom - box.bottom;
    geometryById.set(element.id, { ...element.geometry, x: rounded(element.geometry.x + dx), y: rounded(element.geometry.y + dy) });
  });
  return updateTargets(document, slideId, targetIds, (element) => ({
    ...element,
    geometry: geometryById.get(element.id) ?? element.geometry
  }));
}
function distributeElements(document, slideId, targetIds, axis) {
  const index = indexDocumentElements(document);
  const entries = targetIds.map((id) => {
    const element = index.get(id).element;
    return { element, box: rotatedBoundingBox(element.geometry, element.transform?.rotation) };
  }).sort((a, b) => axis === "horizontal" ? a.box.left - b.box.left : a.box.top - b.box.top);
  const first = entries[0].box;
  const last = entries[entries.length - 1].box;
  const totalSize = entries.reduce((sum, entry) => sum + (axis === "horizontal" ? entry.box.right - entry.box.left : entry.box.bottom - entry.box.top), 0);
  const span = axis === "horizontal" ? last.right - first.left : last.bottom - first.top;
  const gap = (span - totalSize) / (entries.length - 1);
  let cursor = axis === "horizontal" ? first.left : first.top;
  const geometryById = /* @__PURE__ */ new Map();
  for (const entry of entries) {
    const size = axis === "horizontal" ? entry.box.right - entry.box.left : entry.box.bottom - entry.box.top;
    const delta = cursor - (axis === "horizontal" ? entry.box.left : entry.box.top);
    geometryById.set(entry.element.id, {
      ...entry.element.geometry,
      x: rounded(entry.element.geometry.x + (axis === "horizontal" ? delta : 0)),
      y: rounded(entry.element.geometry.y + (axis === "vertical" ? delta : 0))
    });
    cursor += size + gap;
  }
  return updateTargets(document, slideId, targetIds, (element) => ({ ...element, geometry: geometryById.get(element.id) }));
}
function indexSlide(slide) {
  const document = { slides: [slide] };
  return indexDocumentElements(document);
}
function assertValidResult(document) {
  const validation = validatePresentationDocument(document);
  if (!validation.ok) {
    const issue = validation.issues[0];
    throw new EditorCommandError("EDITOR_COMMAND_RESULT_INVALID", void 0, `${issue?.code ?? "CANONICAL_SCHEMA_INVALID"}:${issue?.path ?? "$"}`);
  }
  return validation.document;
}
function rounded(value) {
  return Math.round(value * 1e6) / 1e6;
}
export {
  applyCommandBatch,
  canonicalChecksum,
  canonicalJson
};
