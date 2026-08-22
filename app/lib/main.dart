import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'theme/app_theme.dart';
import 'screens/splash_screen.dart';
import 'screens/auth/phone_input_screen.dart';
import 'screens/auth/otp_verify_screen.dart';
import 'screens/home_screen.dart';
import 'screens/camera_screen.dart';
import 'screens/preview_screen.dart';
import 'screens/history_screen.dart';
import 'screens/info_screen.dart';
import 'screens/account_screen.dart';
import 'screens/server_setup_screen.dart';
import 'screens/screening_report_screen.dart';
import 'services/screening_history_service.dart';
import 'widgets/bottom_nav_bar.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
  ));

  runApp(const HemoScanApp());
}

class HemoScanApp extends StatelessWidget {
  const HemoScanApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'HemoScan AI',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      initialRoute: '/',
      onGenerateRoute: _generateRoute,
    );
  }

  Route<dynamic>? _generateRoute(RouteSettings settings) {
    switch (settings.name) {
      case '/':
        return MaterialPageRoute(builder: (_) => const SplashScreen());

      case '/auth/phone':
        return MaterialPageRoute(builder: (_) => const PhoneInputScreen());

      case '/auth/otp':
        final phone = settings.arguments as String;
        return MaterialPageRoute(
          builder: (_) => OtpVerifyScreen(phoneNumber: phone),
        );

      case '/main':
        return MaterialPageRoute(builder: (_) => const MainShell());

      case '/account':
        return MaterialPageRoute(builder: (_) => const AccountScreen());

      case '/server-setup':
        return MaterialPageRoute(
          builder: (_) => const ServerSetupScreen(isSettings: true),
        );

      case '/camera':
        return MaterialPageRoute(builder: (_) => const CameraScreen());

      case '/preview':
        final imagePath = settings.arguments as String;
        return MaterialPageRoute(
          builder: (_) => PreviewScreen(imagePath: imagePath),
        );

      case '/info':
        return MaterialPageRoute(builder: (_) => const InfoScreen());

      case '/report':
        final record = settings.arguments as ScreeningRecord;
        return MaterialPageRoute(
          builder: (_) => ScreeningReportScreen(record: record),
        );

      default:
        return MaterialPageRoute(builder: (_) => const SplashScreen());
    }
  }
}

/// Main shell with bottom navigation bar.
///
/// Contains Home, (Screen placeholder), History, and Info tabs.
/// The "Screen" tab launches the camera as a full-screen push.
class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => MainShellState();
}

class MainShellState extends State<MainShell> {
  int _currentIndex = 0;

  void switchToTab(int index) {
    setState(() => _currentIndex = index);
  }

  void _onTabTapped(int index) {
    if (index == 1) {
      // "Screen" tab → launch camera
      Navigator.pushNamed(context, '/camera');
      return;
    }
    setState(() => _currentIndex = index);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: [
          HomeScreen(
            onStartScreening: () => Navigator.pushNamed(context, '/camera'),
          ),
          // Placeholder — camera is pushed as a separate screen
          const SizedBox.shrink(),
          const HistoryScreen(),
          const InfoScreen(),
        ],
      ),
      bottomNavigationBar: AppBottomNavBar(
        currentIndex: _currentIndex,
        onTap: _onTabTapped,
      ),
    );
  }
}
