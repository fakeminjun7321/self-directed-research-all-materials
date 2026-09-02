import Cocoa
import SceneKit

struct Atom {
    let name: String
    let residue: Int
    let x: CGFloat
    let y: CGFloat
    let z: CGFloat
}

struct Box {
    let x: CGFloat
    let y: CGFloat
    let z: CGFloat
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private var sceneView: SCNView!
    private var scene: SCNScene!
    private var statusLabel: NSTextField!

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1100, height: 820),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Water MD Viewer"
        window.center()

        sceneView = SCNView(frame: window.contentView!.bounds)
        sceneView.autoresizingMask = [.width, .height]
        sceneView.allowsCameraControl = true
        sceneView.backgroundColor = NSColor(calibratedRed: 0.03, green: 0.04, blue: 0.055, alpha: 1.0)
        sceneView.rendersContinuously = true
        window.contentView?.addSubview(sceneView)

        statusLabel = NSTextField(labelWithString: "")
        statusLabel.textColor = NSColor(white: 0.93, alpha: 0.95)
        statusLabel.font = NSFont.monospacedSystemFont(ofSize: 13, weight: .medium)
        statusLabel.frame = NSRect(x: 18, y: 16, width: 720, height: 22)
        statusLabel.autoresizingMask = [.maxXMargin, .maxYMargin]
        window.contentView?.addSubview(statusLabel)

        scene = SCNScene()
        sceneView.scene = scene

        let pdbPath = Bundle.main.path(forResource: "nvt_final", ofType: "pdb")
        if let pdbPath, let data = try? String(contentsOfFile: pdbPath, encoding: .utf8) {
            loadPDB(data, label: "nvt_final.pdb")
        } else {
            statusLabel.stringValue = "nvt_final.pdb not found in app bundle"
        }

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func loadPDB(_ pdb: String, label: String) {
        let parsed = parsePDB(pdb)
        guard !parsed.atoms.isEmpty else {
            statusLabel.stringValue = "No atoms found in \(label)"
            return
        }

        let center = centerOf(parsed.atoms)
        let scale: CGFloat = 0.085
        let atomRoot = SCNNode()
        atomRoot.name = "Atoms"
        scene.rootNode.addChildNode(atomRoot)

        let oxygenMaterial = material(NSColor(calibratedRed: 0.95, green: 0.16, blue: 0.13, alpha: 1.0))
        let hydrogenMaterial = material(NSColor(calibratedRed: 0.94, green: 0.96, blue: 1.0, alpha: 1.0))
        let bondMaterial = material(NSColor(calibratedRed: 0.72, green: 0.77, blue: 0.85, alpha: 1.0))
        let boxMaterial = material(NSColor(calibratedRed: 0.28, green: 0.68, blue: 1.0, alpha: 0.52))

        for atom in parsed.atoms {
            let isOxygen = atom.name.uppercased().hasPrefix("O")
            let radius: CGFloat = isOxygen ? 0.07 : 0.038
            let sphere = SCNSphere(radius: radius)
            sphere.segmentCount = isOxygen ? 18 : 12
            sphere.firstMaterial = isOxygen ? oxygenMaterial : hydrogenMaterial

            let node = SCNNode(geometry: sphere)
            node.position = vector(atom, center: center, scale: scale)
            atomRoot.addChildNode(node)
        }

        addWaterBonds(parsed.atoms, center: center, scale: scale, material: bondMaterial, root: atomRoot)

        if let box = parsed.box {
            addBox(box, center: center, scale: scale, material: boxMaterial)
        }

        addLighting()
        addCamera()

        statusLabel.stringValue = "\(label)  |  \(parsed.atoms.count) atoms  |  \(parsed.atoms.count / 3) waters"
    }

    private func parsePDB(_ text: String) -> (atoms: [Atom], box: Box?) {
        var atoms: [Atom] = []
        var box: Box?

        for line in text.split(separator: "\n", omittingEmptySubsequences: false) {
            let s = String(line)
            if s.hasPrefix("CRYST1") {
                let parts = s.split(whereSeparator: { $0 == " " || $0 == "\t" })
                if parts.count >= 4,
                   let x = Double(parts[1]),
                   let y = Double(parts[2]),
                   let z = Double(parts[3]) {
                    box = Box(x: CGFloat(x), y: CGFloat(y), z: CGFloat(z))
                }
            }

            guard s.hasPrefix("ATOM") || s.hasPrefix("HETATM") else { continue }
            let name = slice(s, 12, 16).trimmingCharacters(in: .whitespaces)
            let residue = Int(slice(s, 22, 26).trimmingCharacters(in: .whitespaces)) ?? atoms.count / 3
            guard
                let x = Double(slice(s, 30, 38).trimmingCharacters(in: .whitespaces)),
                let y = Double(slice(s, 38, 46).trimmingCharacters(in: .whitespaces)),
                let z = Double(slice(s, 46, 54).trimmingCharacters(in: .whitespaces))
            else { continue }

            atoms.append(Atom(name: name, residue: residue, x: CGFloat(x), y: CGFloat(y), z: CGFloat(z)))
        }

        return (atoms, box)
    }

    private func slice(_ string: String, _ start: Int, _ end: Int) -> String {
        let chars = Array(string)
        guard chars.count > start else { return "" }
        let lower = max(0, start)
        let upper = min(chars.count, end)
        guard lower < upper else { return "" }
        return String(chars[lower..<upper])
    }

    private func centerOf(_ atoms: [Atom]) -> SCNVector3 {
        var minX = CGFloat.greatestFiniteMagnitude
        var minY = CGFloat.greatestFiniteMagnitude
        var minZ = CGFloat.greatestFiniteMagnitude
        var maxX = -CGFloat.greatestFiniteMagnitude
        var maxY = -CGFloat.greatestFiniteMagnitude
        var maxZ = -CGFloat.greatestFiniteMagnitude

        for atom in atoms {
            minX = min(minX, atom.x)
            minY = min(minY, atom.y)
            minZ = min(minZ, atom.z)
            maxX = max(maxX, atom.x)
            maxY = max(maxY, atom.y)
            maxZ = max(maxZ, atom.z)
        }

        return SCNVector3((minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2)
    }

    private func vector(_ atom: Atom, center: SCNVector3, scale: CGFloat) -> SCNVector3 {
        let x = (atom.x - center.x) * scale
        let y = (atom.y - center.y) * scale
        let z = (atom.z - center.z) * scale
        return SCNVector3(x, y, z)
    }

    private func material(_ color: NSColor) -> SCNMaterial {
        let material = SCNMaterial()
        material.diffuse.contents = color
        material.specular.contents = NSColor(white: 0.85, alpha: 1.0)
        material.shininess = 0.35
        return material
    }

    private func addWaterBonds(_ atoms: [Atom], center: SCNVector3, scale: CGFloat, material: SCNMaterial, root: SCNNode) {
        let grouped = Dictionary(grouping: atoms, by: { $0.residue })
        for (_, residueAtoms) in grouped {
            guard let oxygen = residueAtoms.first(where: { $0.name.uppercased().hasPrefix("O") }) else { continue }
            let oxygenVector = vector(oxygen, center: center, scale: scale)

            for hydrogen in residueAtoms where hydrogen.name.uppercased().hasPrefix("H") {
                let hydrogenVector = vector(hydrogen, center: center, scale: scale)
                let rawDistance = distance(SCNVector3(oxygen.x, oxygen.y, oxygen.z), SCNVector3(hydrogen.x, hydrogen.y, hydrogen.z))
                if rawDistance < 1.3 {
                    root.addChildNode(cylinder(from: oxygenVector, to: hydrogenVector, radius: 0.012, material: material))
                }
            }
        }
    }

    private func addBox(_ box: Box, center: SCNVector3, scale: CGFloat, material: SCNMaterial) {
        func corner(_ x: CGFloat, _ y: CGFloat, _ z: CGFloat) -> SCNVector3 {
            SCNVector3((x - center.x) * scale, (y - center.y) * scale, (z - center.z) * scale)
        }

        let corners: [SCNVector3] = [
            corner(0, 0, 0),
            corner(box.x, 0, 0),
            corner(box.x, box.y, 0),
            corner(0, box.y, 0),
            corner(0, 0, box.z),
            corner(box.x, 0, box.z),
            corner(box.x, box.y, box.z),
            corner(0, box.y, box.z)
        ]

        let edges = [(0,1), (1,2), (2,3), (3,0), (4,5), (5,6), (6,7), (7,4), (0,4), (1,5), (2,6), (3,7)]
        let root = SCNNode()
        root.name = "Simulation Box"
        for edge in edges {
            root.addChildNode(cylinder(from: corners[edge.0], to: corners[edge.1], radius: 0.006, material: material))
        }
        scene.rootNode.addChildNode(root)
    }

    private func cylinder(from start: SCNVector3, to end: SCNVector3, radius: CGFloat, material: SCNMaterial) -> SCNNode {
        let length = distance(start, end)
        let geometry = SCNCylinder(radius: radius, height: CGFloat(length))
        geometry.radialSegmentCount = 10
        geometry.firstMaterial = material

        let node = SCNNode(geometry: geometry)
        node.position = SCNVector3((start.x + end.x) / 2, (start.y + end.y) / 2, (start.z + end.z) / 2)

        let direction = normalize(SCNVector3(end.x - start.x, end.y - start.y, end.z - start.z))
        let yAxis = SCNVector3(0, 1, 0)
        let axis = cross(yAxis, direction)
        let axisLength = distance(axis, SCNVector3(0, 0, 0))
        let dotValue = max(-1, min(1, dot(yAxis, direction)))

        if axisLength < 0.0001 {
            if dotValue < 0 {
                node.rotation = SCNVector4(1, 0, 0, CGFloat.pi)
            }
        } else {
            node.rotation = SCNVector4(axis.x / axisLength, axis.y / axisLength, axis.z / axisLength, acos(dotValue))
        }

        return node
    }

    private func addLighting() {
        let ambient = SCNLight()
        ambient.type = .ambient
        ambient.intensity = 450
        let ambientNode = SCNNode()
        ambientNode.light = ambient
        scene.rootNode.addChildNode(ambientNode)

        let key = SCNLight()
        key.type = .omni
        key.intensity = 950
        let keyNode = SCNNode()
        keyNode.light = key
        keyNode.position = SCNVector3(4, 5, 7)
        scene.rootNode.addChildNode(keyNode)
    }

    private func addCamera() {
        let camera = SCNCamera()
        camera.zNear = 0.01
        camera.zFar = 100
        camera.fieldOfView = 45

        let cameraNode = SCNNode()
        cameraNode.camera = camera
        cameraNode.position = SCNVector3(0, 0, 6.2)
        scene.rootNode.addChildNode(cameraNode)
        sceneView.pointOfView = cameraNode
    }

    private func distance(_ a: SCNVector3, _ b: SCNVector3) -> CGFloat {
        let dx = a.x - b.x
        let dy = a.y - b.y
        let dz = a.z - b.z
        let squared = dx * dx + dy * dy + dz * dz
        return sqrt(squared)
    }

    private func normalize(_ value: SCNVector3) -> SCNVector3 {
        let length = max(distance(value, SCNVector3(0, 0, 0)), 0.000001)
        return SCNVector3(value.x / length, value.y / length, value.z / length)
    }

    private func cross(_ a: SCNVector3, _ b: SCNVector3) -> SCNVector3 {
        SCNVector3(
            a.y * b.z - a.z * b.y,
            a.z * b.x - a.x * b.z,
            a.x * b.y - a.y * b.x
        )
    }

    private func dot(_ a: SCNVector3, _ b: SCNVector3) -> CGFloat {
        let xy = a.x * b.x + a.y * b.y
        return xy + a.z * b.z
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
