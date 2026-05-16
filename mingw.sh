x86_64-w64-mingw32-g++ -shared -o myserver.dll main.cpp game.cpp hook.cpp server.cpp flag.cpp aob_scanner.cpp -I. -lws2_32 -lmswsock -lcrypt32 -static -static-libgcc -static-libstdc++ -lpthread
