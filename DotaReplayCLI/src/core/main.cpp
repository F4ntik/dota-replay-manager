#include <iostream>
#include <string>
#include <windows.h> // Required for GetModuleHandle

#include "core/app.h"       // For Application class and getApp()
#include "replay/replay.h"
#include "present.h" // Updated to actual filename present.h moved to src/core/

// Global config object, typically initialized by Application constructor
// extern Cfg cfg; // Declaration might be needed if cfg is used directly and not through app object methods

int main(int argc, char* argv[]) {
    // Initialize the Application object. This sets up getApp(), cfg, DotaLibrary, CacheManager etc.
    // For a console application, many HINSTANCE/HWND parameters are not relevant.
    // Using GetModuleHandle(NULL) for hInstance. Other params can be NULL/empty.
    Application app(GetModuleHandle(NULL), NULL, "", 0);

    // Check if the application loaded correctly (e.g. resources, configurations)
    // The Application constructor in app.cpp has a logCommand check that might exit early
    // if it misinterprets argv. However, we pass "" for lpCmdLine to Application,
    // so it should proceed to full initialization.
    // A more robust check would be if app.loaded() is true, if such a method exists
    // or if critical components like getDotaLibrary() return non-null.
    // For now, we assume initialization proceeds sufficiently for W3GReplay::load.

    if (argc != 2) {
        std::cerr << "Usage: DotAReplayPresentation <path_to_replay_file>" << std::endl;
        return 1;
    }

    char* replayPath = argv[1];
    uint32 error = 0;

    // Ensure underlying systems W3GReplay::load() depends on are initialized by 'app' instance.
    W3GReplay* replay = W3GReplay::load(replayPath, 0, &error);

    if (replay == nullptr || error != 0) {
        std::cerr << "Error: Could not load replay file: " << replayPath;
        if (error == W3GReplay::eNoFile) {
            std::cerr << " (File not found or could not be opened)";
        } else if (error == W3GReplay::eBadFile) {
            std::cerr << " (Bad replay file format or corrupted)";
        } else if (error == W3GReplay::eNoMap) {
            std::cerr << " (Map data not found or could not be loaded)";
        } else if (error != 0) {
            std::cerr << " (Unknown error code: " << error << ")";
        }
        std::cerr << std::endl;
        // W3GReplay::load is expected to return nullptr on error,
        // and handle deallocation of partially created objects itself.
        // delete replay; // Should not be needed if replay is nullptr.
        return 1;
    }

    // Assuming PresentationGenerator is correctly defined in "ui/replay/PresentGen.h"
    // If PresentationGenerator itself depends on getApp() or cfg, it should work now.
    PresentationGenerator generator(replay); 
    std::string presentation_output = generator.generate();
    std::cout << presentation_output << std::endl;

    delete replay; // Clean up the replay object

    // The 'app' object will be destroyed when main exits, calling its destructor,
    // which should clean up resources like DotaLibrary, CacheManager etc.

    return 0;
}
