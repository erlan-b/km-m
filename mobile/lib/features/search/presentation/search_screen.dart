import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../../listings/data/categories_repository.dart';
import '../../listings/data/listings_repository.dart';
import '../../listings/presentation/widgets/listing_card.dart';

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _searchCtrl = TextEditingController();
  List<dynamic> _results = [];
  List<dynamic> _categories = [];
  bool _loading = false;
  String? _error;
  int _page = 1;
  int _totalPages = 1;

  // Filter state
  int? _selectedCategoryId;
  String? _selectedCity;
  double? _minPrice;
  double? _maxPrice;
  String _sortBy = 'newest';

  @override
  void initState() {
    super.initState();
    _loadCategories();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadCategories() async {
    try {
      final cats = await ref.read(categoriesRepositoryProvider).getCategories(activeOnly: true);
      setState(() { _categories = cats; });
    } catch (_) {}
  }

  Future<void> _search({bool append = false}) async {
    if (!append) {
      _page = 1;
      setState(() { _loading = true; _error = null; });
    }

    try {
      final repo = ref.read(listingsRepositoryProvider);
      final data = await repo.getListings(
        page: _page,
        pageSize: 20,
        query: _searchCtrl.text.trim().isNotEmpty ? _searchCtrl.text.trim() : null,
        categoryId: _selectedCategoryId,
        city: _selectedCity,
        minPrice: _minPrice,
        maxPrice: _maxPrice,
        sortBy: _sortBy,
        status: 'published',
      );
      final items = data['items'] as List<dynamic>;
      setState(() {
        if (append) {
          _results.addAll(items);
        } else {
          _results = items;
        }
        _totalPages = data['total_pages'] as int;
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  void _loadMore() {
    if (_page < _totalPages) {
      _page++;
      _search(append: true);
    }
  }

  void _showFilterSheet() {
    final l = S.of(context)!;
    final minCtrl = TextEditingController(text: _minPrice?.toStringAsFixed(0));
    final maxCtrl = TextEditingController(text: _maxPrice?.toStringAsFixed(0));
    final cityCtrl = TextEditingController(text: _selectedCity);
    int? tempCatId = _selectedCategoryId;
    String tempSort = _sortBy;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) => Padding(
          padding: EdgeInsets.fromLTRB(20, 20, 20, MediaQuery.of(ctx).viewInsets.bottom + 20),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(l.filters, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                    TextButton(
                      onPressed: () {
                        setSheetState(() {
                          tempCatId = null;
                          tempSort = 'newest';
                          minCtrl.clear();
                          maxCtrl.clear();
                          cityCtrl.clear();
                        });
                      },
                      child: Text(l.reset),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Category
                Text(l.category, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    ChoiceChip(
                      label: Text(l.allCategories),
                      selected: tempCatId == null,
                      onSelected: (_) => setSheetState(() => tempCatId = null),
                    ),
                    ..._categories.map((cat) {
                      final id = cat['id'] as int;
                      final name = cat['name'] as String;
                      return ChoiceChip(
                        label: Text(name),
                        selected: tempCatId == id,
                        onSelected: (_) => setSheetState(() => tempCatId = id),
                      );
                    }),
                  ],
                ),
                const SizedBox(height: 16),

                // City
                Text(l.city, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 6),
                TextField(controller: cityCtrl, decoration: InputDecoration(hintText: l.city)),
                const SizedBox(height: 16),

                // Price range
                Text(l.price, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Expanded(child: TextField(controller: minCtrl, keyboardType: TextInputType.number, decoration: InputDecoration(hintText: l.minPrice))),
                    const SizedBox(width: 12),
                    Expanded(child: TextField(controller: maxCtrl, keyboardType: TextInputType.number, decoration: InputDecoration(hintText: l.maxPrice))),
                  ],
                ),
                const SizedBox(height: 16),

                // Sort
                Text(l.sort, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    for (final entry in {'newest': l.newest, 'oldest': l.oldest, 'price_asc': l.priceAsc, 'price_desc': l.priceDesc, 'most_viewed': l.mostViewed}.entries)
                      ChoiceChip(
                        label: Text(entry.value),
                        selected: tempSort == entry.key,
                        onSelected: (_) => setSheetState(() => tempSort = entry.key),
                      ),
                  ],
                ),
                const SizedBox(height: 24),

                ElevatedButton(
                  onPressed: () {
                    setState(() {
                      _selectedCategoryId = tempCatId;
                      _selectedCity = cityCtrl.text.trim().isNotEmpty ? cityCtrl.text.trim() : null;
                      _minPrice = double.tryParse(minCtrl.text);
                      _maxPrice = double.tryParse(maxCtrl.text);
                      _sortBy = tempSort;
                    });
                    Navigator.pop(ctx);
                    _search();
                  },
                  child: Text(l.apply),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(l.search),
      ),
      body: Column(
        children: [
          // Search bar + filter button
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _searchCtrl,
                    decoration: InputDecoration(
                      hintText: l.search,
                      prefixIcon: const Icon(Icons.search, size: 20),
                      contentPadding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
                      isDense: true,
                    ),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _search(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: _showFilterSheet,
                  icon: const Icon(Icons.tune, size: 20),
                  style: IconButton.styleFrom(
                    backgroundColor: AppTheme.accent,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTheme.radius)),
                  ),
                ),
              ],
            ),
          ),
          // Results
          Expanded(child: _buildResults(l)),
        ],
      ),
    );
  }

  Widget _buildResults(S l) {
    if (_loading && _results.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.accent));
    }

    if (_error != null && _results.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48, color: AppTheme.textSubtle),
            const SizedBox(height: 12),
            Text(l.errorOccurred, style: const TextStyle(color: AppTheme.textSubtle)),
            const SizedBox(height: 12),
            ElevatedButton(onPressed: () => _search(), child: Text(l.retry)),
          ],
        ),
      );
    }

    if (_results.isEmpty && !_loading) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.search_off, size: 48, color: AppTheme.textSubtle),
            const SizedBox(height: 12),
            Text(l.noResults, style: const TextStyle(color: AppTheme.textSubtle)),
          ],
        ),
      );
    }

    return NotificationListener<ScrollNotification>(
      onNotification: (notification) {
        if (notification is ScrollEndNotification && notification.metrics.extentAfter < 200) {
          _loadMore();
        }
        return false;
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: GridView.builder(
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 0.68,
          ),
          itemCount: _results.length,
          itemBuilder: (context, index) {
            final listing = _results[index] as Map<String, dynamic>;
            return ListingCard(
              id: listing['id'] as int,
              title: listing['title'] as String,
              price: (listing['price'] is String)
                  ? double.parse(listing['price'] as String)
                  : (listing['price'] as num).toDouble(),
              currency: listing['currency'] as String,
              city: listing['city'] as String,
              transactionType: listing['transaction_type'] as String,
              onTap: () => context.push('/listing/${listing['id']}'),
            );
          },
        ),
      ),
    );
  }
}
